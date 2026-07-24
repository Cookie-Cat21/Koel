"""Exact pinned-Qlib LightGBM and DoubleEnsemble adapters."""

from __future__ import annotations

from typing import Any

from koel.ml.dataset import Sample


class _StaticSegmentDataset:
    def __init__(self, frames: dict[str, Any]) -> None:
        self.frames = frames
        self.segments = {name: name for name in frames}

    def prepare(
        self,
        segment: str | list[str],
        col_set: str | list[str] | None = None,
        data_key: str | None = None,
    ) -> Any:
        _ = data_key
        if isinstance(segment, list):
            return [self.prepare(name, col_set, data_key) for name in segment]
        frame = self.frames[segment]
        return frame if col_set is None else frame.loc[:, col_set]


def _frame(samples: list[Sample]) -> Any:
    import numpy as np
    import pandas as pd

    index = pd.MultiIndex.from_tuples(
        [(sample.as_of, sample.symbol) for sample in samples],
        names=("datetime", "instrument"),
    )
    feature_count = len(samples[0].x)
    features = pd.DataFrame(
        np.asarray([sample.x for sample in samples], dtype=float),
        index=index,
        columns=[f"f{column:03d}" for column in range(feature_count)],
    )
    labels = pd.DataFrame(
        np.asarray([sample.y_ret for sample in samples], dtype=float),
        index=index,
        columns=("label",),
    )
    return pd.concat({"feature": features, "label": labels}, axis=1)


def _split_train_valid(samples: list[Sample]) -> tuple[list[Sample], list[Sample]]:
    dates = sorted({sample.as_of for sample in samples})
    valid_days = max(10, int(len(dates) * 0.10))
    valid_dates = set(dates[-valid_days:])
    fit = [sample for sample in samples if sample.as_of not in valid_dates]
    valid = [sample for sample in samples if sample.as_of in valid_dates]
    return fit, valid


def predict_exact_qlib(
    train: list[Sample],
    test: list[Sample],
    *,
    model_name: str,
    provider_uri: str,
    seed: int,
) -> list[float]:
    """Fit an exact ``pyqlib==0.9.7`` model against Koel sample frames."""
    if model_name not in {"qlib_lgb_exact", "qlib_double_ensemble_exact"}:
        raise ValueError("unsupported exact Qlib model")
    if not train or not test:
        raise ValueError("exact Qlib model requires train and test rows")

    import numpy as np
    import qlib
    from qlib.config import REG_US
    from qlib.contrib.model.double_ensemble import DEnsembleModel
    from qlib.contrib.model.gbdt import LGBModel

    qlib.init(
        provider_uri=provider_uri,
        region=REG_US,
        expression_cache=None,
        dataset_cache=None,
    )
    fit, valid = _split_train_valid(train)
    dataset = _StaticSegmentDataset(
        {
            "train": _frame(fit),
            "valid": _frame(valid),
            "test": _frame(test),
        }
    )
    params = {
        "colsample_bytree": 0.8879,
        "learning_rate": 0.05,
        "subsample": 0.8789,
        "lambda_l1": 205.6999,
        "lambda_l2": 580.9768,
        "max_depth": 8,
        "num_leaves": 210,
        "num_threads": 4,
        "seed": seed,
        "feature_fraction_seed": seed,
        "bagging_seed": seed,
        "data_random_seed": seed,
        "deterministic": True,
        "force_col_wise": True,
        "verbosity": -1,
    }
    np.random.seed(seed)
    if model_name == "qlib_lgb_exact":
        model = LGBModel(
            loss="mse",
            early_stopping_rounds=50,
            num_boost_round=1000,
            **params,
        )
        model.fit(dataset, verbose_eval=0)
    else:
        model = DEnsembleModel(
            base_model="gbm",
            loss="mse",
            num_models=3,
            enable_sr=True,
            enable_fs=True,
            alpha1=1.0,
            alpha2=1.0,
            bins_sr=10,
            bins_fs=5,
            decay=0.5,
            sample_ratios=[0.8, 0.7, 0.6, 0.5, 0.4],
            sub_weights=[1.0, 1.0, 1.0],
            epochs=28,
            early_stopping_rounds=50,
            **params,
        )
        model.fit(dataset)
    prediction = model.predict(dataset, segment="test")
    by_key = {
        (index[0].date() if hasattr(index[0], "date") else index[0], str(index[1])): float(value)
        for index, value in prediction.items()
    }
    return [by_key[(sample.as_of, sample.symbol)] for sample in test]
