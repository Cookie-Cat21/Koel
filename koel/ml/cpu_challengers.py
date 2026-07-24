"""Additional CPU challenger backends for the exhaustive search ladder.

These stay lazy-imported (heavy deps only inside function bodies) so the
module is safe to import in environments without lightgbm/xgboost.
"""

from __future__ import annotations

import os

from koel.ml.challengers import _chronological_fit_valid_indices, _matrices
from koel.ml.dataset import Sample


def _as_sample_weight(sample_weight: object | None, expected: int) -> object | None:
    if sample_weight is None:
        return None
    import numpy as np

    weights = np.asarray(sample_weight, dtype=float)
    if weights.shape != (expected,):
        raise ValueError("sample_weight must align to train samples")
    return weights


def predict_ridge_return(
    train: list[Sample],
    test: list[Sample],
    *,
    seed: int,
    sample_weight: object | None = None,
) -> list[float]:
    """L2-regularized linear return regression (strong CPU baseline)."""
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    x_train, x_test, y_train = _matrices(train, test)
    weights = _as_sample_weight(sample_weight, len(train))
    model = make_pipeline(
        StandardScaler(),
        Ridge(alpha=10.0, random_state=seed),
    )
    fit_kwargs = {} if weights is None else {"ridge__sample_weight": weights}
    model.fit(x_train, y_train, **fit_kwargs)
    return [float(value) for value in model.predict(x_test)]


def predict_hgb_regressor(
    train: list[Sample],
    test: list[Sample],
    *,
    seed: int,
    sample_weight: object | None = None,
) -> list[float]:
    """HistGradientBoosting return regression."""
    from sklearn.ensemble import HistGradientBoostingRegressor

    x_train, x_test, y_train = _matrices(train, test)
    weights = _as_sample_weight(sample_weight, len(train))
    model = HistGradientBoostingRegressor(
        learning_rate=0.05,
        max_depth=6,
        max_iter=300,
        l2_regularization=1.0,
        random_state=seed,
    )
    model.fit(x_train, y_train, sample_weight=weights)
    return [float(value) for value in model.predict(x_test)]


def predict_xgb_regressor(
    train: list[Sample],
    test: list[Sample],
    *,
    seed: int,
    sample_weight: object | None = None,
) -> list[float]:
    """XGBoost hist return regression."""
    from xgboost import XGBRegressor

    x_train, x_test, y_train = _matrices(train, test)
    weights = _as_sample_weight(sample_weight, len(train))
    model = XGBRegressor(
        n_estimators=400,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.85,
        colsample_bytree=0.85,
        min_child_weight=20,
        reg_lambda=2.0,
        tree_method="hist",
        n_jobs=max(1, int(os.environ.get("ML_WORKER_THREADS", "4"))),
        random_state=seed,
    )
    model.fit(x_train, y_train, sample_weight=weights)
    return [float(value) for value in model.predict(x_test)]


def predict_hgb_bagged(
    train: list[Sample],
    test: list[Sample],
    *,
    seed: int,
    n_bags: int = 5,
    sample_weight: object | None = None,
) -> list[float]:
    """Bagged direction HGB (averages probability margins across bags)."""
    import numpy as np
    from sklearn.ensemble import HistGradientBoostingClassifier

    selected = [sample for sample in train if sample.y_dir != 0]
    if len(selected) < 100:
        raise ValueError("insufficient train samples for hgb_bagged")
    x_train, x_test, _ = _matrices(selected, test)
    weights_by_id = (
        None
        if sample_weight is None
        else {id(sample): weight for sample, weight in zip(train, sample_weight, strict=True)}
    )
    weights = (
        None
        if weights_by_id is None
        else _as_sample_weight([weights_by_id[id(sample)] for sample in selected], len(selected))
    )
    y_train = np.asarray(
        [1 if sample.y_dir > 0 else 0 for sample in selected], dtype=int
    )
    if len(set(y_train.tolist())) < 2:
        raise ValueError("training split contains one class")
    acc = np.zeros(len(test), dtype=float)
    rng = np.random.RandomState(seed)
    for bag in range(n_bags):
        indices = rng.randint(0, len(selected), size=len(selected))
        model = HistGradientBoostingClassifier(
            learning_rate=0.05,
            max_depth=6,
            max_iter=200,
            l2_regularization=1.0,
            random_state=seed + bag,
        )
        model.fit(
            x_train[indices],
            y_train[indices],
            sample_weight=None if weights is None else weights[indices],
        )
        acc += model.predict_proba(x_test)[:, 1]
    return [float(value / n_bags - 0.5) for value in acc]


def predict_hgb_deep(
    train: list[Sample],
    test: list[Sample],
    *,
    seed: int,
    sample_weight: object | None = None,
) -> list[float]:
    """Deeper/longer HGB direction classifier."""
    import numpy as np
    from sklearn.ensemble import HistGradientBoostingClassifier

    selected = [sample for sample in train if sample.y_dir != 0]
    if len(selected) < 100:
        raise ValueError("insufficient train samples for hgb_deep")
    x_train, x_test, _ = _matrices(selected, test)
    weights_by_id = (
        None
        if sample_weight is None
        else {id(sample): weight for sample, weight in zip(train, sample_weight, strict=True)}
    )
    weights = (
        None
        if weights_by_id is None
        else _as_sample_weight([weights_by_id[id(sample)] for sample in selected], len(selected))
    )
    y_train = np.asarray(
        [1 if sample.y_dir > 0 else 0 for sample in selected], dtype=int
    )
    model = HistGradientBoostingClassifier(
        learning_rate=0.03,
        max_depth=8,
        max_iter=400,
        l2_regularization=2.0,
        random_state=seed,
    )
    model.fit(x_train, y_train, sample_weight=weights)
    return [float(value - 0.5) for value in model.predict_proba(x_test)[:, 1]]


def predict_hgb_weighted(
    train: list[Sample],
    test: list[Sample],
    *,
    seed: int,
    sample_weight: object | None = None,
) -> list[float]:
    """Direction HGB with |return|-magnitude sample weights."""
    import numpy as np
    from sklearn.ensemble import HistGradientBoostingClassifier

    selected = [sample for sample in train if sample.y_dir != 0]
    if len(selected) < 100:
        raise ValueError("insufficient train samples for hgb_weighted")
    x_train, x_test, _ = _matrices(selected, test)
    y_train = np.asarray(
        [1 if sample.y_dir > 0 else 0 for sample in selected], dtype=int
    )
    weights = np.asarray([abs(sample.y_ret) for sample in selected], dtype=float)
    weights_by_id = (
        None
        if sample_weight is None
        else {id(sample): weight for sample, weight in zip(train, sample_weight, strict=True)}
    )
    if weights_by_id is not None:
        weights *= np.asarray([weights_by_id[id(sample)] for sample in selected], dtype=float)
    mean = float(np.mean(weights))
    if mean > 0:
        weights = weights / mean
    model = HistGradientBoostingClassifier(
        learning_rate=0.05,
        max_depth=6,
        max_iter=250,
        l2_regularization=1.0,
        random_state=seed,
    )
    model.fit(x_train, y_train, sample_weight=weights)
    return [float(value - 0.5) for value in model.predict_proba(x_test)[:, 1]]


def predict_lgb_tuned(
    train: list[Sample],
    test: list[Sample],
    *,
    seed: int,
    learning_rate: float = 0.05,
    max_depth: int = 8,
    num_leaves: int = 127,
    subsample: float = 0.85,
    colsample_bytree: float = 0.9,
    reg_lambda: float = 50.0,
    n_estimators: int = 600,
    sample_weight: object | None = None,
) -> list[float]:
    """Configurable LightGBM return regressor used by the 10k calibration screen."""
    import lightgbm as lgb
    import numpy as np
    from lightgbm import LGBMRegressor

    x_train, x_test, y_train = _matrices(train, test)
    fit_indices, valid_indices = _chronological_fit_valid_indices(train)
    weights = _as_sample_weight(sample_weight, len(train))
    model = LGBMRegressor(
        objective="regression",
        n_estimators=n_estimators,
        learning_rate=learning_rate,
        max_depth=max_depth,
        num_leaves=num_leaves,
        colsample_bytree=colsample_bytree,
        subsample=subsample,
        subsample_freq=1,
        reg_lambda=reg_lambda,
        random_state=seed,
        n_jobs=max(1, int(os.environ.get("ML_WORKER_THREADS", "4"))),
        deterministic=True,
        force_col_wise=True,
        verbosity=-1,
    )
    fit_kwargs = {}
    if valid_indices:
        fit_kwargs = {
            "eval_X": x_train[np.asarray(valid_indices)],
            "eval_y": y_train[np.asarray(valid_indices)],
            "callbacks": [lgb.early_stopping(40, verbose=False)],
        }
    model.fit(
        x_train[np.asarray(fit_indices)],
        y_train[np.asarray(fit_indices)],
        sample_weight=(
            None if weights is None else weights[np.asarray(fit_indices)]
        ),
        **fit_kwargs,
    )
    return [float(value) for value in model.predict(x_test)]


def predict_xgb_rank_pairwise(
    train: list[Sample],
    test: list[Sample],
    *,
    seed: int,
) -> list[float]:
    from koel.ml.ltr_dual import _predict_xgb_rank

    del seed  # upstream helper is deterministic given data order
    return _predict_xgb_rank(train, test, objective="rank:pairwise")


def predict_xgb_rank_ndcg(
    train: list[Sample],
    test: list[Sample],
    *,
    seed: int,
) -> list[float]:
    from koel.ml.ltr_dual import _predict_xgb_rank

    del seed
    return _predict_xgb_rank(train, test, objective="rank:ndcg")


def predict_lgb_lambdarank(
    train: list[Sample],
    test: list[Sample],
    *,
    seed: int,
) -> list[float]:
    from koel.ml.ltr_dual import _predict_lgb_rank

    del seed
    return _predict_lgb_rank(train, test)


def predict_blend_de_lgb(
    train: list[Sample],
    test: list[Sample],
    *,
    seed: int,
    sample_weight: object | None = None,
) -> list[float]:
    """Equal blend of native DoubleEnsemble and Qlib-parameter LightGBM."""
    from koel.ml.challengers import (
        predict_native_double_ensemble,
        predict_qlib_lightgbm,
    )

    a = predict_native_double_ensemble(
        train,
        test,
        seed=seed,
        sample_weight=sample_weight,
    )
    b = predict_qlib_lightgbm(train, test, seed=seed, sample_weight=sample_weight)
    return [0.5 * (x + y) for x, y in zip(a, b, strict=True)]


def predict_blend_de_ridge(
    train: list[Sample],
    test: list[Sample],
    *,
    seed: int,
    sample_weight: object | None = None,
) -> list[float]:
    """Equal blend of DoubleEnsemble and Ridge."""
    from koel.ml.challengers import predict_native_double_ensemble

    a = predict_native_double_ensemble(
        train,
        test,
        seed=seed,
        sample_weight=sample_weight,
    )
    b = predict_ridge_return(train, test, seed=seed, sample_weight=sample_weight)
    return [0.5 * (x + y) for x, y in zip(a, b, strict=True)]


CPU_EXHAUST_MODELS: tuple[str, ...] = (
    "logistic",
    "ridge_return",
    "hgb_lmt",
    "hgb_deep",
    "hgb_bagged",
    "hgb_weighted",
    "hgb_domain",
    "hgb_two_stage",
    "hgb_regressor",
    "xgb_lmt",
    "xgb_domain",
    "xgb_two_stage",
    "xgb_regressor",
    "xgb_rank_pairwise",
    "xgb_rank_ndcg",
    "lgb_lmt",
    "lgb_domain",
    "lgb_lambdarank",
    "qlib_lgb_native",
    "double_ensemble_native",
    "blend_de_lgb",
    "blend_de_ridge",
)


def lgb_hyperparam_grid(*, limit: int = 10_000) -> list[dict[str, float | int]]:
    """Predeclared 10k LightGBM grid; selection must use calibration only."""
    learning_rates = (0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.10, 0.12, 0.15)
    max_depths = (4, 5, 6, 7, 8)
    num_leaves = (15, 31, 63, 95, 127, 159, 191, 255)
    subsamples = (0.6, 0.7, 0.8, 0.85, 0.9)
    reg_lambdas = (1.0, 5.0, 20.0, 50.0, 100.0)
    grid: list[dict[str, float | int]] = []
    for learning_rate in learning_rates:
        for max_depth in max_depths:
            for leaves in num_leaves:
                for subsample in subsamples:
                    for reg_lambda in reg_lambdas:
                        grid.append(
                            {
                                "learning_rate": learning_rate,
                                "max_depth": max_depth,
                                "num_leaves": leaves,
                                "subsample": subsample,
                                "colsample_bytree": min(0.95, subsample + 0.05),
                                "reg_lambda": reg_lambda,
                            }
                        )
                        if len(grid) >= limit:
                            return grid
    return grid[:limit]

