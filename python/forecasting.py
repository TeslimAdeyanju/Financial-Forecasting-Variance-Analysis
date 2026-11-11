"""Stage 4: monthly net-spend forecasting with walk-forward (expanding window) validation.

Every model predicts month t using only information available at the end of
month t-1. Features come from gold_monthly_spend, which is built backward-looking.
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from statsmodels.tsa.statespace.sarimax import SARIMAX
from xgboost import XGBRegressor

import config

TARGET = "net_spend"
FEATURES = [
    "lag_1_month",
    "lag_2_month",
    "lag_3_month",
    "lag_12_month",
    "rolling_mean_3_months",
    "rolling_mean_6_months",
    "rolling_std_6_months",
    "month",
]
SARIMA_ORDER = (1, 1, 1)
SARIMA_SEASONAL = (0, 1, 1, 12)


def prepare(monthly: pd.DataFrame) -> pd.DataFrame:
    """Complete months only, indexed by month_start, sorted."""
    df = monthly.loc[monthly["is_complete_month"]].copy()
    df["month_start"] = pd.to_datetime(df["month_start"])
    return df.sort_values("month_start").set_index("month_start").asfreq("MS")


def _xgb() -> XGBRegressor:
    return XGBRegressor(
        objective="reg:squarederror", n_estimators=300, max_depth=3, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8, random_state=config.RANDOM_STATE, verbosity=0,
    )


def _sarima_fit(history: pd.Series):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return SARIMAX(history, order=SARIMA_ORDER, seasonal_order=SARIMA_SEASONAL,
                       enforce_stationarity=False, enforce_invertibility=False).fit(disp=False)


def walk_forward(df: pd.DataFrame, test_months: int = 24) -> pd.DataFrame:
    """One-step-ahead predictions for the last `test_months` months, one row per month."""
    model_rows = df.dropna(subset=FEATURES)
    test_index = model_rows.index[-test_months:]
    rows = []
    for month in test_index:
        history = df.loc[df.index < month, TARGET]
        train = model_rows.loc[model_rows.index < month]
        xgb = _xgb().fit(train[FEATURES], train[TARGET])
        rows.append(
            {
                "month_start": month,
                "actual": df.at[month, TARGET],
                "Naive (last month)": df.at[month, "lag_1_month"],
                "Seasonal naive (same month last year)": df.at[month, "lag_12_month"],
                "SARIMA": float(_sarima_fit(history).forecast(1).iloc[0]),
                "XGBoost": float(xgb.predict(df.loc[[month], FEATURES])[0]),
            }
        )
    return pd.DataFrame(rows).set_index("month_start")


def score(predictions: pd.DataFrame) -> pd.DataFrame:
    y = predictions["actual"]
    out = []
    for model in predictions.columns.drop("actual"):
        p = predictions[model]
        out.append(
            {
                "model": model,
                "MAE": mean_absolute_error(y, p),
                "RMSE": float(np.sqrt(mean_squared_error(y, p))),
                "MAPE_pct": float(np.mean(np.abs((y - p) / y)) * 100),
                "R2": r2_score(y, p),
            }
        )
    return pd.DataFrame(out).sort_values("MAPE_pct").reset_index(drop=True)


def final_xgb(df: pd.DataFrame) -> tuple[XGBRegressor, pd.DataFrame]:
    """XGBoost refit on all usable months (used for SHAP interpretation)."""
    rows = df.dropna(subset=FEATURES)
    return _xgb().fit(rows[FEATURES], rows[TARGET]), rows[FEATURES]


def forecast_ahead(df: pd.DataFrame, horizon: int = 12, alpha: float = 0.05) -> pd.DataFrame:
    """Forward forecast with prediction intervals, from SARIMA fitted on all complete months.

    SARIMA is used for the forward view because it produces model-based prediction
    intervals; XGBoost would need recursive feature generation and has no native interval.
    """
    fit = _sarima_fit(df[TARGET])
    fc = fit.get_forecast(horizon)
    ci = fc.conf_int(alpha=alpha)
    return pd.DataFrame(
        {"forecast": fc.predicted_mean, "lower": ci.iloc[:, 0], "upper": ci.iloc[:, 1]}
    ).rename_axis("month_start")
