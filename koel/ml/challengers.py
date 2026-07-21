"""CPU challenger backends inspired by Qlib benchmark configurations."""

from __future__ import annotations

import math

from koel.ml.dataset import Sample


def _matrices(
    train: list[Sample],
    test: list[Sample],
) -> tuple[object, object, object]:
    import numpy as np

    x_train = np.asarray([sample.x for sample in train], dtype=float)
    x_test = np.asarray([sample.x for sample in test], dtype=float)
    y_train = np.asarray([sample.y_ret for sample in train], dtype=float)
    x_train[~np.isfinite(x_train)] = np.nan
    x_test[~np.isfinite(x_test)] = np.nan
    medians = np.nanmedian(x_train, axis=0)
    medians = np.where(np.isfinite(medians), medians, 0.0)
    for matrix in (x_train, x_test):
        missing = np.where(np.isnan(matrix))
        matrix[missing] = np.take(medians, missing[1])
    varying = np.ptp(x_train, axis=0) > 1e-12
    if not np.any(varying):
        raise ValueError("challenger training split has no varying features")
    return x_train[:, varying], x_test[:, varying], y_train


def _chronological_fit_valid_indices(samples: list[Sample]) -> tuple[list[int], list[int]]:
    dates = sorted({sample.as_of for sample in samples})
    if len(dates) < 20:
        split = max(1, int(len(samples) * 0.9))
        return list(range(split)), list(range(split, len(samples)))
    valid_days = max(10, math.ceil(len(dates) * 0.10))
    valid_dates = set(dates[-valid_days:])
    fit = [index for index, sample in enumerate(samples) if sample.as_of not in valid_dates]
    valid = [index for index, sample in enumerate(samples) if sample.as_of in valid_dates]
    return fit, valid


def predict_qlib_lightgbm(
    train: list[Sample],
    test: list[Sample],
    *,
    seed: int,
) -> list[float]:
    """Qlib-parameter-style LightGBM return regression baseline."""
    import lightgbm as lgb
    import numpy as np
    from lightgbm import LGBMRegressor

    x_train, x_test, y_train = _matrices(train, test)
    fit_indices, valid_indices = _chronological_fit_valid_indices(train)
    model = LGBMRegressor(
        objective="regression",
        n_estimators=1000,
        learning_rate=0.05,
        max_depth=8,
        num_leaves=210,
        colsample_bytree=0.8879,
        subsample=0.8789,
        subsample_freq=1,
        reg_alpha=205.6999,
        reg_lambda=580.9768,
        random_state=seed,
        n_jobs=4,
        deterministic=True,
        force_col_wise=True,
        verbosity=-1,
    )
    fit_kwargs = {}
    if valid_indices:
        fit_kwargs = {
            "eval_X": x_train[np.asarray(valid_indices)],
            "eval_y": y_train[np.asarray(valid_indices)],
            "callbacks": [lgb.early_stopping(50, verbose=False)],
        }
    model.fit(
        x_train[np.asarray(fit_indices)],
        y_train[np.asarray(fit_indices)],
        **fit_kwargs,
    )
    return [float(value) for value in model.predict(x_test)]


def predict_native_double_ensemble(
    train: list[Sample],
    test: list[Sample],
    *,
    seed: int,
) -> list[float]:
    """Deterministic native approximation of Qlib's DoubleEnsemble concept.

    Exact parity remains an isolated ``pyqlib==0.9.7`` workflow task.
    """
    import numpy as np
    from lightgbm import LGBMRegressor

    x_train, x_test, y_train = _matrices(train, test)
    feature_count = x_train.shape[1]
    correlations = []
    y_std = float(np.std(y_train))
    for index in range(feature_count):
        column = x_train[:, index]
        if float(np.std(column)) == 0 or y_std == 0:
            correlations.append(0.0)
        else:
            value = float(np.corrcoef(column, y_train)[0, 1])
            correlations.append(abs(value) if math.isfinite(value) else 0.0)
    ranked_features = np.argsort(np.asarray(correlations))[::-1]

    sample_weight = np.ones(len(train), dtype=float)
    predictions = []
    for model_index, ratio in enumerate((1.0, 0.8, 0.6)):
        selected_n = max(1, math.ceil(feature_count * ratio))
        selected = ranked_features[:selected_n]
        model = LGBMRegressor(
            objective="regression",
            n_estimators=500,
            learning_rate=0.05,
            max_depth=8,
            num_leaves=127,
            colsample_bytree=0.90,
            subsample=0.85,
            subsample_freq=1,
            reg_lambda=50.0,
            random_state=seed + model_index,
            n_jobs=4,
            deterministic=True,
            force_col_wise=True,
            verbosity=-1,
        )
        model.fit(
            x_train[:, selected],
            y_train,
            sample_weight=sample_weight,
        )
        train_prediction = model.predict(x_train[:, selected])
        error = np.abs(y_train - train_prediction)
        scale = float(np.median(error))
        if scale > 0:
            sample_weight = np.clip(1.0 + error / scale, 1.0, 5.0)
            sample_weight /= float(np.mean(sample_weight))
        predictions.append(model.predict(x_test[:, selected]))
    mean_prediction = np.mean(np.asarray(predictions), axis=0)
    return [float(value) for value in mean_prediction]
