"""GPU challenger adapters (TRA, MASTER, Kronos-as-features).

Each adapter follows the lazy-import convention used throughout
``koel/ml`` (see ``koel/ml/qlib_exact.py``): no heavy dependency is
imported at module load time, only inside the function body, so this
module can be imported even when torch/qlib/Kronos are not installed.

Pinned upstream revisions (see ``koel/ml/challenger_catalog.py``):

- ``qlib_tra``: TRA from pinned ``pyqlib==0.9.7``
  (Qlib release commit ``da920b7f954f48ab1bb64117c976710de198373e``, MIT).
  Reuses Qlib's own ``TRAModel``/``TRA``/``RNN`` classes unmodified; only
  the data-glue (a minimal ``DataHandler`` stub feeding a static
  Koel-``Sample``-derived frame into ``MTSDatasetH``) is Koel-specific,
  mirroring the ``_StaticSegmentDataset`` pattern already used for the
  exact Qlib LightGBM/DoubleEnsemble adapters.
"""

from __future__ import annotations

from typing import Any

from koel.ml.dataset import Sample


def _split_train_valid(samples: list[Sample]) -> tuple[list[Sample], list[Sample]]:
    dates = sorted({sample.as_of for sample in samples})
    valid_days = max(10, int(len(dates) * 0.10))
    valid_dates = set(dates[-valid_days:])
    fit = [sample for sample in samples if sample.as_of not in valid_dates]
    valid = [sample for sample in samples if sample.as_of in valid_dates]
    return fit, valid


def _tra_frame(samples: list[Sample]) -> Any:
    """Build the Qlib-shaped (datetime, instrument) feature/label frame.

    Samples are sorted by (instrument, datetime) prior to the
    ``MultiIndex`` construction so that, after ``MTSDatasetH`` internally
    swaps levels back to <instrument, datetime> and slices positionally
    per instrument, each window only ever contains that instrument's own
    strictly-preceding rows -- no cross-symbol leakage and no lookahead.
    """
    import numpy as np
    import pandas as pd

    ordered = sorted(samples, key=lambda sample: (sample.symbol, sample.as_of))
    index = pd.MultiIndex.from_tuples(
        [(pd.Timestamp(sample.as_of), sample.symbol) for sample in ordered],
        names=("datetime", "instrument"),
    )
    feature_count = len(ordered[0].x)
    # Single float32 array + MultiIndex columns, built directly rather than
    # via pd.concat({"feature": ..., "label": ...}) -- concat's internal
    # block-manager reindex/copy step roughly doubles peak memory versus
    # this, which matters at hybrid-dataset scale (hundreds of thousands
    # of rows once Yahoo-sourced history is included alongside CSE).
    # MTSDatasetH casts to float32 internally anyway (see its setup_data),
    # so building it that way here avoids a second float64->float32 copy.
    data = np.empty((len(ordered), feature_count + 1), dtype=np.float32)
    data[:, :feature_count] = [sample.x for sample in ordered]
    data[:, feature_count] = [sample.y_ret for sample in ordered]
    columns = pd.MultiIndex.from_tuples(
        [("feature", f"f{column:03d}") for column in range(feature_count)]
        + [("label", "label")]
    )
    return pd.DataFrame(data, index=index, columns=columns)


def _make_static_handler(frame: Any) -> Any:
    """A ``qlib.data.dataset.handler.DataHandler`` stub for ``MTSDatasetH``.

    ``MTSDatasetH.setup_data`` only ever reads ``handler._learn`` (falling
    back to ``handler._data``); it never calls ``handler.fetch`` or
    ``handler.setup_data``. Subclassing (rather than duck-typing) is
    required so ``qlib.utils.init_instance_by_config(handler,
    accept_types=DataHandler)`` accepts the instance unchanged.
    """
    from qlib.data.dataset.handler import DataHandler

    class _StaticHandler(DataHandler):
        def __init__(self, static_frame: Any) -> None:  # noqa: D401 - stub
            self._learn = static_frame
            self._data = static_frame

    return _StaticHandler(frame)


def predict_qlib_tra(
    train: list[Sample],
    test: list[Sample],
    *,
    seed: int,
    horizon: int = 1,
    seq_len: int = 20,
    num_states: int = 3,
    n_epochs: int = 30,
    batch_size: int = 64,
) -> list[float]:
    """Fit pinned-Qlib's ``TRAModel`` (RNN backbone + router) on Koel samples.

    Config is predeclared and fixed across folds/seeds (paper-inspired
    defaults scaled down from Qlib's Alpha360 example config to fit a 6GB
    GPU and the much smaller CSE instrument universe): ``seq_len=20``,
    RNN backbone (hidden_size=64, 2 layers, attention), TRA router with
    3 latent states, ``transport_method="router"``. Only ``seed`` varies
    per run, per the no-tuning-on-test-labels contract.
    """
    if not train or not test:
        raise ValueError("qlib_tra requires train and test rows")

    import numpy as np
    import torch
    from qlib.contrib.data.dataset import MTSDatasetH
    from qlib.contrib.model.pytorch_tra import TRAModel

    torch.manual_seed(seed)
    np.random.seed(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    fit, valid = _split_train_valid(train)
    if not fit or not valid:
        raise ValueError("qlib_tra requires both fit and validation rows")

    all_samples = fit + valid + test
    frame = _tra_frame(all_samples)
    handler = _make_static_handler(frame)

    segments = {
        "train": (min(s.as_of for s in fit), max(s.as_of for s in fit)),
        "valid": (min(s.as_of for s in valid), max(s.as_of for s in valid)),
        "test": (min(s.as_of for s in test), max(s.as_of for s in test)),
    }
    dataset = MTSDatasetH(
        handler=handler,
        segments=segments,
        seq_len=seq_len,
        horizon=horizon,
        num_states=num_states,
        memory_mode="sample",
        batch_size=batch_size,
        n_samples=None,
        shuffle=True,
        drop_last=False,
    )

    input_size = len(all_samples[0].x)
    model_config = {
        "input_size": input_size,
        "hidden_size": 64,
        "num_layers": 2,
        "rnn_arch": "GRU",
        "use_attn": True,
        "dropout": 0.1,
    }
    tra_config = {
        "num_states": num_states,
        "hidden_size": 16,
        "rnn_arch": "GRU",
        "num_layers": 1,
        "tau": 1.0,
        "src_info": "LR_TPE",
    }
    model = TRAModel(
        model_config=model_config,
        tra_config=tra_config,
        model_type="RNN",
        lr=1e-3,
        n_epochs=n_epochs,
        early_stop=8,
        max_steps_per_epoch=100,
        lamb=0.5,
        rho=0.99,
        alpha=1.0,
        seed=seed,
        transport_method="router",
        memory_mode="sample",
    )
    model.fit(dataset)
    prediction = model.predict(dataset, segment="test")

    by_key = {
        (index[0].date() if hasattr(index[0], "date") else index[0], str(index[1])): float(
            row["score"]
        )
        for index, row in prediction.iterrows()
    }
    return [by_key[(sample.as_of, sample.symbol)] for sample in test]


# ---------------------------------------------------------------------------
# MASTER (vendored architecture, pinned revision de8f58557096abde4216a701b3
# 5fc4368158d111 of https://github.com/SJTU-DMTai/MASTER, MIT license).
#
# The classes below (``PositionalEncoding``, ``SAttention``, ``TAttention``,
# ``Gate``, ``TemporalAttention``, ``_MasterNet``) are the upstream
# ``master.py`` architecture at that revision, copied verbatim apart from a
# rename (``MASTER`` -> ``_MasterNet``, to avoid clashing with this file's
# public adapter name) and dropping the ``SequenceModel``/``DailyBatch
# SamplerRandom``/``DataLoader`` training scaffolding, which this adapter
# reimplements directly against Koel ``Sample`` windows instead (see
# ``_windowed_by_symbol``/``predict_master`` below).
# ---------------------------------------------------------------------------


def _build_master_net(torch_module: Any) -> type:
    nn = torch_module.nn
    math_module = __import__("math")

    class PositionalEncoding(nn.Module):
        def __init__(self, d_model: int, max_len: int = 100) -> None:
            super().__init__()
            pe = torch_module.zeros(max_len, d_model)
            position = torch_module.arange(0, max_len, dtype=torch_module.float).unsqueeze(1)
            div_term = torch_module.exp(
                torch_module.arange(0, d_model, 2).float()
                * (-math_module.log(10000.0) / d_model)
            )
            pe[:, 0::2] = torch_module.sin(position * div_term)
            pe[:, 1::2] = torch_module.cos(position * div_term)
            self.register_buffer("pe", pe)

        def forward(self, x: Any) -> Any:
            return x + self.pe[: x.shape[1], :]

    class SAttention(nn.Module):
        def __init__(self, d_model: int, nhead: int, dropout: float) -> None:
            super().__init__()
            self.d_model = d_model
            self.nhead = nhead
            self.temperature = math_module.sqrt(self.d_model / nhead)
            self.qtrans = nn.Linear(d_model, d_model, bias=False)
            self.ktrans = nn.Linear(d_model, d_model, bias=False)
            self.vtrans = nn.Linear(d_model, d_model, bias=False)
            self.attn_dropout = nn.ModuleList(
                [nn.Dropout(p=dropout) for _ in range(nhead)]
            )
            self.norm1 = nn.LayerNorm(d_model, eps=1e-5)
            self.norm2 = nn.LayerNorm(d_model, eps=1e-5)
            self.ffn = nn.Sequential(
                nn.Linear(d_model, d_model),
                nn.ReLU(),
                nn.Dropout(p=dropout),
                nn.Linear(d_model, d_model),
                nn.Dropout(p=dropout),
            )

        def forward(self, x: Any) -> Any:
            x = self.norm1(x)
            q = self.qtrans(x).transpose(0, 1)
            k = self.ktrans(x).transpose(0, 1)
            v = self.vtrans(x).transpose(0, 1)
            dim = int(self.d_model / self.nhead)
            att_output = []
            for i in range(self.nhead):
                if i == self.nhead - 1:
                    qh, kh, vh = q[:, :, i * dim :], k[:, :, i * dim :], v[:, :, i * dim :]
                else:
                    qh = q[:, :, i * dim : (i + 1) * dim]
                    kh = k[:, :, i * dim : (i + 1) * dim]
                    vh = v[:, :, i * dim : (i + 1) * dim]
                atten = torch_module.softmax(
                    torch_module.matmul(qh, kh.transpose(1, 2)) / self.temperature, dim=-1
                )
                atten = self.attn_dropout[i](atten)
                att_output.append(torch_module.matmul(atten, vh).transpose(0, 1))
            att_output = torch_module.concat(att_output, dim=-1)
            xt = x + att_output
            xt = self.norm2(xt)
            return xt + self.ffn(xt)

    class TAttention(nn.Module):
        def __init__(self, d_model: int, nhead: int, dropout: float) -> None:
            super().__init__()
            self.d_model = d_model
            self.nhead = nhead
            self.qtrans = nn.Linear(d_model, d_model, bias=False)
            self.ktrans = nn.Linear(d_model, d_model, bias=False)
            self.vtrans = nn.Linear(d_model, d_model, bias=False)
            self.attn_dropout = nn.ModuleList(
                [nn.Dropout(p=dropout) for _ in range(nhead)]
            )
            self.norm1 = nn.LayerNorm(d_model, eps=1e-5)
            self.norm2 = nn.LayerNorm(d_model, eps=1e-5)
            self.ffn = nn.Sequential(
                nn.Linear(d_model, d_model),
                nn.ReLU(),
                nn.Dropout(p=dropout),
                nn.Linear(d_model, d_model),
                nn.Dropout(p=dropout),
            )

        def forward(self, x: Any) -> Any:
            x = self.norm1(x)
            q, k, v = self.qtrans(x), self.ktrans(x), self.vtrans(x)
            dim = int(self.d_model / self.nhead)
            att_output = []
            for i in range(self.nhead):
                if i == self.nhead - 1:
                    qh, kh, vh = q[:, :, i * dim :], k[:, :, i * dim :], v[:, :, i * dim :]
                else:
                    qh = q[:, :, i * dim : (i + 1) * dim]
                    kh = k[:, :, i * dim : (i + 1) * dim]
                    vh = v[:, :, i * dim : (i + 1) * dim]
                atten = torch_module.softmax(torch_module.matmul(qh, kh.transpose(1, 2)), dim=-1)
                atten = self.attn_dropout[i](atten)
                att_output.append(torch_module.matmul(atten, vh))
            att_output = torch_module.concat(att_output, dim=-1)
            xt = x + att_output
            xt = self.norm2(xt)
            return xt + self.ffn(xt)

    class Gate(nn.Module):
        def __init__(self, d_input: int, d_output: int, beta: float = 1.0) -> None:
            super().__init__()
            self.trans = nn.Linear(d_input, d_output)
            self.d_output = d_output
            self.t = beta

        def forward(self, gate_input: Any) -> Any:
            output = self.trans(gate_input)
            output = torch_module.softmax(output / self.t, dim=-1)
            return self.d_output * output

    class TemporalAttention(nn.Module):
        def __init__(self, d_model: int) -> None:
            super().__init__()
            self.trans = nn.Linear(d_model, d_model, bias=False)

        def forward(self, z: Any) -> Any:
            h = self.trans(z)
            query = h[:, -1, :].unsqueeze(-1)
            lam = torch_module.matmul(h, query).squeeze(-1)
            lam = torch_module.softmax(lam, dim=1).unsqueeze(1)
            return torch_module.matmul(lam, z).squeeze(1)

    class _MasterNet(nn.Module):
        def __init__(
            self,
            d_feat: int,
            d_model: int,
            t_nhead: int,
            s_nhead: int,
            t_dropout_rate: float,
            s_dropout_rate: float,
            gate_input_start_index: int,
            gate_input_end_index: int,
            beta: float,
        ) -> None:
            super().__init__()
            self.gate_input_start_index = gate_input_start_index
            self.gate_input_end_index = gate_input_end_index
            self.d_gate_input = gate_input_end_index - gate_input_start_index
            self.feature_gate = Gate(self.d_gate_input, d_feat, beta=beta)
            self.layers = nn.Sequential(
                nn.Linear(d_feat, d_model),
                PositionalEncoding(d_model),
                TAttention(d_model=d_model, nhead=t_nhead, dropout=t_dropout_rate),
                SAttention(d_model=d_model, nhead=s_nhead, dropout=s_dropout_rate),
                TemporalAttention(d_model=d_model),
                nn.Linear(d_model, 1),
            )

        def forward(self, x: Any) -> Any:
            src = x[:, :, : self.gate_input_start_index]
            gate_input = x[:, -1, self.gate_input_start_index : self.gate_input_end_index]
            src = src * torch_module.unsqueeze(self.feature_gate(gate_input), dim=1)
            return self.layers(src).squeeze(-1)

    return _MasterNet


def _windowed_by_symbol(samples: list[Sample], seq_len: int) -> dict[tuple[str, Any], Any]:
    """Per-symbol, strictly-backward, zero-padded feature windows.

    Mirrors ``qlib``'s own ``_create_ts_slices``/``_maybe_padding`` logic
    (see ``predict_qlib_tra`` above): each window for ``(symbol, as_of)``
    contains only that symbol's own rows up to and including ``as_of``,
    left-padded with zeros when fewer than ``seq_len`` prior rows exist.
    """
    import numpy as np

    by_symbol: dict[str, list[Sample]] = {}
    for sample in samples:
        by_symbol.setdefault(sample.symbol, []).append(sample)

    feature_count = len(samples[0].x)
    zero_row = np.zeros(feature_count, dtype=np.float32)
    windows: dict[tuple[str, Any], Any] = {}
    for symbol, rows in by_symbol.items():
        ordered = sorted(rows, key=lambda s: s.as_of)
        vectors = [np.asarray(s.x, dtype=np.float32) for s in ordered]
        for index, sample in enumerate(ordered):
            start = max(0, index - seq_len + 1)
            history = vectors[start : index + 1]
            if len(history) < seq_len:
                history = [zero_row] * (seq_len - len(history)) + history
            windows[(symbol, sample.as_of)] = np.stack(history, axis=0)
    return windows


def predict_master(
    train: list[Sample],
    test: list[Sample],
    *,
    seed: int,
    seq_len: int = 20,
    d_model: int = 64,
    t_nhead: int = 4,
    s_nhead: int = 2,
    dropout: float = 0.1,
    beta: float = 5.0,
    n_epochs: int = 30,
    lr: float = 1e-3,
    market_context_width: int = 5,
) -> list[float]:
    """Fit pinned-revision MASTER (market-gated dual attention) on samples.

    ``market_context_width`` slices off the trailing
    ``MARKET_CONTEXT_NAMES`` block that ``koel.ml.research_features
    .enrich_market_context`` appends last to every ``Sample.x`` -- those
    columns feed MASTER's feature gate, matching the paper's market-status
    gating mechanism. Config is predeclared (paper-inspired, scaled down
    for a 6GB GPU and CSE's smaller universe) and fixed across
    folds/seeds; only ``seed`` varies.
    """
    if not train or not test:
        raise ValueError("master requires train and test rows")

    import numpy as np
    import torch

    torch.manual_seed(seed)
    np.random.seed(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    fit, valid = _split_train_valid(train)
    if not fit or not valid:
        raise ValueError("master requires both fit and validation rows")

    feature_count = len(train[0].x)
    if market_context_width >= feature_count:
        raise ValueError("market_context_width must be smaller than the feature count")
    gate_start = feature_count - market_context_width
    gate_end = feature_count

    all_samples = fit + valid + test
    windows = _windowed_by_symbol(all_samples, seq_len)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    def _segment_tensors(segment: list[Sample]) -> tuple[list[Sample], Any, Any]:
        ordered = sorted(segment, key=lambda s: (s.as_of, s.symbol))
        x = np.stack([windows[(s.symbol, s.as_of)] for s in ordered], axis=0)
        y = np.asarray([s.y_ret for s in ordered], dtype=np.float32)
        return ordered, torch.from_numpy(x), torch.from_numpy(y)

    fit_order, fit_x, fit_y = _segment_tensors(fit)
    valid_order, valid_x, valid_y = _segment_tensors(valid)
    test_order, test_x, test_y = _segment_tensors(test)

    def _day_boundaries(ordered: list[Sample]) -> list[tuple[int, int]]:
        bounds = []
        start = 0
        for index in range(1, len(ordered) + 1):
            if index == len(ordered) or ordered[index].as_of != ordered[start].as_of:
                bounds.append((start, index))
                start = index
        return bounds

    fit_days = _day_boundaries(fit_order)
    valid_days = _day_boundaries(valid_order)
    test_days = _day_boundaries(test_order)

    net_cls = _build_master_net(torch)
    model = net_cls(
        d_feat=gate_start,
        d_model=d_model,
        t_nhead=t_nhead,
        s_nhead=s_nhead,
        t_dropout_rate=dropout,
        s_dropout_rate=dropout,
        gate_input_start_index=gate_start,
        gate_input_end_index=gate_end,
        beta=beta,
    ).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)

    fit_x, fit_y = fit_x.to(device), fit_y.to(device)
    valid_x, valid_y = valid_x.to(device), valid_y.to(device)
    test_x = test_x.to(device)

    def _zscore(values: Any) -> Any:
        std = values.std()
        if not torch.isfinite(std) or std < 1e-8:
            return values - values.mean()
        return (values - values.mean()) / std

    def _valid_rank_ic() -> float:
        model.eval()
        with torch.no_grad():
            preds = []
            for start, end in valid_days:
                preds.append(model(valid_x[start:end].float()))
            pred = torch.cat(preds).cpu().numpy()
        label = valid_y.cpu().numpy()
        if pred.std() < 1e-12 or label.std() < 1e-12:
            return 0.0
        from scipy.stats import spearmanr

        correlation = spearmanr(pred, label).statistic
        return float(correlation) if correlation == correlation else 0.0

    rng = np.random.RandomState(seed)
    best_state = None
    best_score = -float("inf")
    patience = 8
    stale = 0
    for _epoch in range(n_epochs):
        model.train()
        order = list(range(len(fit_days)))
        rng.shuffle(order)
        for day_index in order:
            start, end = fit_days[day_index]
            batch_x = fit_x[start:end].float()
            batch_y = _zscore(fit_y[start:end])
            prediction = model(batch_x)
            loss = torch.mean((prediction - batch_y) ** 2)
            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_value_(model.parameters(), 3.0)
            optimizer.step()

        score = _valid_rank_ic()
        if score > best_score:
            best_score = score
            best_state = {key: value.clone() for key, value in model.state_dict().items()}
            stale = 0
        else:
            stale += 1
            if stale >= patience:
                break

    if best_state is not None:
        model.load_state_dict(best_state)

    model.eval()
    with torch.no_grad():
        preds = []
        for start, end in test_days:
            preds.append(model(test_x[start:end].float()))
        scores = torch.cat(preds).cpu().numpy()

    by_key = {
        (sample.as_of, sample.symbol): float(score)
        for sample, score in zip(test_order, scores, strict=True)
    }
    return [by_key[(sample.as_of, sample.symbol)] for sample in test]


# ---------------------------------------------------------------------------
# Kronos-as-features (frozen forecaster; pinned revision
# 67b630e67f6a18c9e9be918d9b4337c960db1e9a of
# https://github.com/shiyu-coder/Kronos, MIT license). Vendored architecture
# lives in ``koel/ml/vendor/kronos/`` (see that package's header comments).
#
# IMPORTANT CONTAMINATION BOUNDARY: the public ``NeoQuasar/Kronos-mini`` and
# ``NeoQuasar/Kronos-small`` checkpoints were pretrained on data through
# June 2024. Their forecast features are only valid evidence for evaluation
# periods strictly after that date -- callers must restrict this adapter's
# use to folds/test windows that satisfy that boundary (the repository's
# official-CSE development folds do).
#
# Kronos itself is used ONLY as a frozen feature generator: no fine-tuning,
# no gradient ever flows into it. Its own ``KronosPredictor.predict`` only
# returns the mean of its internal Monte-Carlo forecast samples, which loses
# the per-sample distribution needed for quantile-width/p(up) -- so this
# adapter reimplements the same generation loop
# (``_kronos_sample_paths``, copied from ``auto_regressive_inference`` in
# the vendored ``kronos.py``, minus its final ``np.mean`` reduction) to keep
# every Monte-Carlo path instead of only their average.
# ---------------------------------------------------------------------------

_KRONOS_CHECKPOINTS = {
    "mini": ("NeoQuasar/Kronos-Tokenizer-2k", "NeoQuasar/Kronos-mini"),
    "small": ("NeoQuasar/Kronos-Tokenizer-base", "NeoQuasar/Kronos-small"),
}


def _reconstruct_price_path(sample: Sample, lookback: int) -> Any:
    """Approximate a daily OHLCV history from ``Sample.x``'s own derived
    features (``log_price``, ``ret_1d/5d/20d/60d``, ``liquidity_20d``,
    ``vol_spike``, ``range_20d``).

    ``Sample`` only carries engineered features, not raw bars, so this is a
    deliberate, documented approximation: geometric interpolation between
    the known trailing-return anchor points reconstructs a plausible
    *shape* for the recent path (which is all Kronos's own z-normalized
    input actually uses -- see ``KronosPredictor.predict``'s
    ``(x - x_mean) / (x_std + 1e-5)`` normalization), not the true history.
    """
    import numpy as np
    import pandas as pd

    from koel.ml.features import FEATURE_NAMES

    index_of = {name: position for position, name in enumerate(FEATURE_NAMES)}
    values = sample.x

    def _feat(name: str, default: float = 0.0) -> float:
        position = index_of.get(name)
        if position is None or position >= len(values):
            return default
        value = values[position]
        return value if value == value else default  # filter NaN

    log_price = _feat("log_price")
    current = float(np.exp(log_price)) if log_price else 1.0
    anchors = {
        0: 1.0,
        1: 1.0 + _feat("ret_1d"),
        5: 1.0 + _feat("ret_5d"),
        20: 1.0 + _feat("ret_20d"),
        60: 1.0 + _feat("ret_60d"),
    }
    days_ago = sorted(anchors, reverse=True)
    relative_at_0 = {0: 1.0}
    for day in days_ago:
        if day == 0:
            continue
        relative_at_0[day] = 1.0 / anchors[day] if anchors[day] > 0 else 1.0

    order = sorted(relative_at_0)
    closes = np.empty(lookback, dtype=np.float64)
    for offset in range(lookback):
        days_before_end = lookback - 1 - offset
        right = next((day for day in order if day >= days_before_end), order[-1])
        left = next((day for day in reversed(order) if day <= days_before_end), order[0])
        if left == right:
            factor = relative_at_0[right]
        else:
            span = right - left
            weight = (days_before_end - left) / span if span else 0.0
            factor = relative_at_0[left] + (relative_at_0[right] - relative_at_0[left]) * weight
        closes[offset] = current * factor

    range_frac = max(_feat("range_20d"), 0.0)
    highs = closes * (1.0 + range_frac / 2)
    lows = closes * (1.0 - range_frac / 2)
    opens = np.roll(closes, 1)
    opens[0] = closes[0]

    liquidity = max(_feat("liquidity_20d"), 1.0)
    vol_spike = max(_feat("vol_spike"), 0.0) or 1.0
    volumes = np.full(lookback, liquidity, dtype=np.float64)
    volumes[-1] = liquidity * vol_spike

    dates = pd.date_range(end=pd.Timestamp(sample.as_of), periods=lookback, freq="B")
    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": volumes},
        index=dates,
    ), current


def _kronos_sample_paths(
    tokenizer: Any,
    model: Any,
    x: Any,
    x_stamp: Any,
    y_stamp: Any,
    *,
    max_context: int,
    pred_len: int,
    sample_count: int,
    clip: int = 5,
    temperature: float = 1.0,
    top_p: float = 0.9,
) -> Any:
    """Copy of ``auto_regressive_inference`` (vendored ``kronos.py``) that
    returns every Monte-Carlo sample path instead of their mean."""
    import torch

    from koel.ml.vendor.kronos.kronos import sample_from_logits

    with torch.no_grad():
        x = torch.clip(x, -clip, clip)
        device = x.device
        x = (
            x.unsqueeze(1)
            .repeat(1, sample_count, 1, 1)
            .reshape(-1, x.size(1), x.size(2))
            .to(device)
        )
        x_stamp = (
            x_stamp.unsqueeze(1)
            .repeat(1, sample_count, 1, 1)
            .reshape(-1, x_stamp.size(1), x_stamp.size(2))
            .to(device)
        )
        y_stamp = (
            y_stamp.unsqueeze(1)
            .repeat(1, sample_count, 1, 1)
            .reshape(-1, y_stamp.size(1), y_stamp.size(2))
            .to(device)
        )

        x_token = tokenizer.encode(x, half=True)
        initial_seq_len = x.size(1)
        batch_size = x_token[0].size(0)
        total_seq_len = initial_seq_len + pred_len
        full_stamp = torch.cat([x_stamp, y_stamp], dim=1)

        generated_pre = x_token[0].new_empty(batch_size, pred_len)
        generated_post = x_token[1].new_empty(batch_size, pred_len)
        pre_buffer = x_token[0].new_zeros(batch_size, max_context)
        post_buffer = x_token[1].new_zeros(batch_size, max_context)
        buffer_len = min(initial_seq_len, max_context)
        if buffer_len > 0:
            start_idx = max(0, initial_seq_len - max_context)
            pre_buffer[:, :buffer_len] = x_token[0][:, start_idx : start_idx + buffer_len]
            post_buffer[:, :buffer_len] = x_token[1][:, start_idx : start_idx + buffer_len]

        for i in range(pred_len):
            current_seq_len = initial_seq_len + i
            window_len = min(current_seq_len, max_context)
            if current_seq_len <= max_context:
                input_tokens = [pre_buffer[:, :window_len], post_buffer[:, :window_len]]
            else:
                input_tokens = [pre_buffer, post_buffer]

            context_end = current_seq_len
            context_start = max(0, context_end - max_context)
            current_stamp = full_stamp[:, context_start:context_end, :].contiguous()

            s1_logits, context = model.decode_s1(input_tokens[0], input_tokens[1], current_stamp)
            s1_logits = s1_logits[:, -1, :]
            sample_pre = sample_from_logits(
                s1_logits, temperature=temperature, top_k=0, top_p=top_p, sample_logits=True
            )
            s2_logits = model.decode_s2(context, sample_pre)
            s2_logits = s2_logits[:, -1, :]
            sample_post = sample_from_logits(
                s2_logits, temperature=temperature, top_k=0, top_p=top_p, sample_logits=True
            )

            generated_pre[:, i] = sample_pre.squeeze(-1)
            generated_post[:, i] = sample_post.squeeze(-1)
            if current_seq_len < max_context:
                pre_buffer[:, current_seq_len] = sample_pre.squeeze(-1)
                post_buffer[:, current_seq_len] = sample_post.squeeze(-1)
            else:
                pre_buffer.copy_(torch.roll(pre_buffer, shifts=-1, dims=1))
                post_buffer.copy_(torch.roll(post_buffer, shifts=-1, dims=1))
                pre_buffer[:, -1] = sample_pre.squeeze(-1)
                post_buffer[:, -1] = sample_post.squeeze(-1)

        full_pre = torch.cat([x_token[0], generated_pre], dim=1)
        full_post = torch.cat([x_token[1], generated_post], dim=1)
        context_start = max(0, total_seq_len - max_context)
        input_tokens = [
            full_pre[:, context_start:total_seq_len].contiguous(),
            full_post[:, context_start:total_seq_len].contiguous(),
        ]
        z = tokenizer.decode(input_tokens, half=True)
        z = z.reshape(-1, sample_count, z.size(1), z.size(2))
        return z.cpu().numpy()  # (batch, sample_count, pred_len_plus_context, channels)


def _kronos_forecast_one(
    tokenizer: Any,
    model: Any,
    device: str,
    price_path: Any,
    current_close: float,
    *,
    pred_len: int,
    sample_count: int,
    max_context: int,
) -> tuple[float, float, float]:
    """Return (median_return, quantile_width, p_up) for one reconstructed
    price path, using every retained Monte-Carlo sample path."""
    import numpy as np
    import pandas as pd
    import torch

    from koel.ml.vendor.kronos.kronos import calc_time_stamps

    price_cols = ["open", "high", "low", "close"]
    df = price_path.copy()
    df["volume"] = df["volume"]
    df["amount"] = df["volume"] * df[price_cols].mean(axis=1)

    x_timestamp = df.index.to_series()
    future_index = pd.date_range(
        start=x_timestamp.iloc[-1], periods=pred_len + 1, freq="B"
    )[1:]
    y_timestamp = future_index.to_series()

    x_time_df = calc_time_stamps(x_timestamp)
    y_time_df = calc_time_stamps(y_timestamp)

    x = df[price_cols + ["volume", "amount"]].values.astype(np.float32)
    x_mean, x_std = np.mean(x, axis=0), np.std(x, axis=0)
    x_norm = (x - x_mean) / (x_std + 1e-5)
    x_norm = np.clip(x_norm, -5, 5)[np.newaxis, :]
    x_stamp = x_time_df.values.astype(np.float32)[np.newaxis, :]
    y_stamp = y_time_df.values.astype(np.float32)[np.newaxis, :]

    x_tensor = torch.from_numpy(x_norm).to(device)
    x_stamp_tensor = torch.from_numpy(x_stamp).to(device)
    y_stamp_tensor = torch.from_numpy(y_stamp).to(device)

    z = _kronos_sample_paths(
        tokenizer,
        model,
        x_tensor,
        x_stamp_tensor,
        y_stamp_tensor,
        max_context=max_context,
        pred_len=pred_len,
        sample_count=sample_count,
    )
    z = z[:, :, -pred_len:, :]
    close_index = price_cols.index("close")
    close_std = x_std[close_index] + 1e-5
    close_mean = x_mean[close_index]
    forecast_closes = z[0, :, -1, close_index] * close_std + close_mean

    forecast_returns = forecast_closes / current_close - 1.0
    forecast_returns = forecast_returns[np.isfinite(forecast_returns)]
    if forecast_returns.size == 0:
        return 0.0, 0.0, 0.5
    median_return = float(np.median(forecast_returns))
    quantile_width = float(
        np.percentile(forecast_returns, 75) - np.percentile(forecast_returns, 25)
    )
    p_up = float(np.mean(forecast_returns > 0))
    return median_return, quantile_width, p_up


def predict_kronos_features(
    train: list[Sample],
    test: list[Sample],
    *,
    seed: int,
    checkpoint: str = "mini",
    pred_len: int = 1,
    sample_count: int = 8,
    lookback: int = 61,
) -> list[float]:
    """Append frozen-Kronos forecast features (median return, quantile
    width, p(up)) to each sample's feature vector, then train/predict with
    the existing pinned-Qlib LightGBM challenger on the augmented vectors.

    Kronos is never fine-tuned; every path here is pure inference from a
    frozen public checkpoint. See the contamination-boundary note above
    this section -- callers must only use this on evaluation windows after
    the checkpoints' June 2024 pretraining cutoff.
    """
    if not train or not test:
        raise ValueError("kronos_features requires train and test rows")
    if checkpoint not in _KRONOS_CHECKPOINTS:
        raise ValueError(f"unknown Kronos checkpoint {checkpoint!r}")

    import torch

    from koel.ml.challengers import predict_qlib_lightgbm
    from koel.ml.vendor.kronos import Kronos, KronosTokenizer

    torch.manual_seed(seed)
    device = "cuda" if torch.cuda.is_available() else "cpu"

    tokenizer_id, model_id = _KRONOS_CHECKPOINTS[checkpoint]
    tokenizer = KronosTokenizer.from_pretrained(tokenizer_id).to(device).eval()
    model = Kronos.from_pretrained(model_id).to(device).eval()
    max_context = 2048 if checkpoint == "mini" else 512

    unique_rows: dict[tuple[str, Any], Sample] = {}
    for sample in train + test:
        unique_rows[(sample.symbol, sample.as_of)] = sample

    forecast_by_key: dict[tuple[str, Any], tuple[float, float, float]] = {}
    for key, sample in unique_rows.items():
        price_path, current_close = _reconstruct_price_path(sample, lookback)
        forecast_by_key[key] = _kronos_forecast_one(
            tokenizer,
            model,
            device,
            price_path,
            current_close,
            pred_len=pred_len,
            sample_count=sample_count,
            max_context=max_context,
        )

    def _augment(samples: list[Sample]) -> list[Sample]:
        augmented = []
        for sample in samples:
            median_return, quantile_width, p_up = forecast_by_key[
                (sample.symbol, sample.as_of)
            ]
            augmented.append(
                Sample(
                    symbol=sample.symbol,
                    as_of=sample.as_of,
                    x=sample.x + (median_return, quantile_width, p_up),
                    y_ret=sample.y_ret,
                    y_dir=sample.y_dir,
                    horizon=sample.horizon,
                    target_date=sample.target_date,
                )
            )
        return augmented

    return predict_qlib_lightgbm(_augment(train), _augment(test), seed=seed)
