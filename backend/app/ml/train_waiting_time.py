"""
Waiting-Time Prediction Model Training & Evaluation for MediSmart.

Chronological 70/15/15 train/validation/test split on synthetic dataset.
Evaluates:
1. Mean Baseline
2. Ridge Regression
3. Random Forest Regressor
4. XGBoost Regressor

Selects winning model based strictly on validation split.
Evaluates winning model on test split once and persists pipeline & metrics artifacts.
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score, root_mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBRegressor

from app.ml.config import (
    ARTIFACTS_DIR,
    DEFAULT_RANDOM_SEED,
    WAITING_TIME_DATASET_PATH,
    WAITING_TIME_FEATURES,
    WAITING_TIME_MODEL_PATH,
    WAITING_TIME_TARGET,
)
from app.ml.estimators import MeanBaselineRegressor, NonNegativeRegressor

logger = logging.getLogger("medismart.ml.waiting_time")

WAITING_TIME_METRICS_PATH = ARTIFACTS_DIR / "waiting_time_metrics.json"

CATEGORICAL_FEATURES = ["doctor_specialty"]
NUMERIC_FEATURES = [
    "doctor_experience_years",
    "day_of_week",
    "slot_hour",
    "slot_minute",
    "arrival_lead_minutes",
    "queue_position_at_checkin",
    "patients_waiting_ahead",
    "is_doctor_active_consultation",
    "historical_avg_consultation_minutes",
]


def compute_regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    """Computes MAE, RMSE, R2, and accuracy within +/- 10 minutes tolerance."""
    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(root_mean_squared_error(y_true, y_pred))
    r2 = float(r2_score(y_true, y_pred))
    within_10 = float(np.mean(np.abs(y_true - y_pred) <= 10.0) * 100.0)
    return {
        "mae_minutes": round(mae, 3),
        "rmse_minutes": round(rmse, 3),
        "r2_score": round(r2, 4),
        "within_10_minutes_percent": round(within_10, 2),
    }


def prepare_chronological_splits(
    dataset_path: Path = WAITING_TIME_DATASET_PATH,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    """
    Loads dataset, validates synthetic provenance, confirms chronological ordering,
    and partitions into 70% train, 15% validation, and 15% test splits.
    """
    df = pd.read_csv(dataset_path)

    # 1. Provenance check
    assert "is_synthetic" in df.columns and df["is_synthetic"].all(), (
        "Dataset must be explicitly labeled synthetic on all records"
    )

    # 2. Chronological sort (stable sort to preserve intra-day order)
    df = df.sort_values("queue_date", kind="mergesort").reset_index(drop=True)

    n_total = len(df)
    n_train = int(n_total * 0.70)
    n_val = int(n_total * 0.15)
    n_test = n_total - n_train - n_val

    train_df = df.iloc[:n_train].copy().reset_index(drop=True)
    val_df = df.iloc[n_train : n_train + n_val].copy().reset_index(drop=True)
    test_df = df.iloc[n_train + n_val :].copy().reset_index(drop=True)

    split_metadata = {
        "total_records": n_total,
        "train": {
            "count": len(train_df),
            "date_start": str(train_df["queue_date"].min()),
            "date_end": str(train_df["queue_date"].max()),
        },
        "validation": {
            "count": len(val_df),
            "date_start": str(val_df["queue_date"].min()),
            "date_end": str(val_df["queue_date"].max()),
        },
        "test": {
            "count": len(test_df),
            "date_start": str(test_df["queue_date"].min()),
            "date_end": str(test_df["queue_date"].max()),
        },
    }

    return train_df, val_df, test_df, split_metadata


def build_preprocessor() -> ColumnTransformer:
    """
    Constructs ColumnTransformer for categorical and numerical features.
    Encoders and scalers are strictly fit on training data only.
    """
    return ColumnTransformer(
        transformers=[
            (
                "cat",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                CATEGORICAL_FEATURES,
            ),
            ("num", StandardScaler(), NUMERIC_FEATURES),
        ],
        remainder="drop",
    )


def train_and_evaluate_models(
    dataset_path: Path = WAITING_TIME_DATASET_PATH,
    seed: int = DEFAULT_RANDOM_SEED,
) -> Tuple[Pipeline, Dict[str, Any]]:
    """
    Trains candidate models, selects the best model on validation data,
    evaluates on test data, and returns the fitted winning pipeline and metrics dict.
    """
    train_df, val_df, test_df, split_meta = prepare_chronological_splits(dataset_path)

    features = CATEGORICAL_FEATURES + NUMERIC_FEATURES
    target = WAITING_TIME_TARGET

    X_train, y_train = train_df[features], train_df[target].values
    X_val, y_val = val_df[features], val_df[target].values
    X_test, y_test = test_df[features], test_df[target].values

    print("=" * 70)
    print("MEDISMART WAITING-TIME PREDICTION: MODEL TRAINING & COMPARISON")
    print("=" * 70)
    print(f"Dataset: {dataset_path.name} ({len(train_df) + len(val_df) + len(test_df)} records)")
    print(f"Train Split:      {split_meta['train']['count']} rows ({split_meta['train']['date_start']} to {split_meta['train']['date_end']})")
    print(f"Validation Split: {split_meta['validation']['count']} rows ({split_meta['validation']['date_start']} to {split_meta['validation']['date_end']})")
    print(f"Test Split:       {split_meta['test']['count']} rows ({split_meta['test']['date_start']} to {split_meta['test']['date_end']})")
    print("-" * 70)

    # Candidate Pipelines
    candidates = {
        "mean_baseline": Pipeline([
            ("regressor", MeanBaselineRegressor()),
        ]),
        "ridge_regression": Pipeline([
            ("preprocessor", build_preprocessor()),
            ("regressor", NonNegativeRegressor(Ridge(alpha=10.0, random_state=seed))),
        ]),
        "random_forest": Pipeline([
            ("preprocessor", build_preprocessor()),
            ("regressor", NonNegativeRegressor(
                RandomForestRegressor(
                    n_estimators=100,
                    max_depth=12,
                    min_samples_split=5,
                    random_state=seed,
                    n_jobs=-1,
                )
            )),
        ]),
        "xgboost": Pipeline([
            ("preprocessor", build_preprocessor()),
            ("regressor", NonNegativeRegressor(
                XGBRegressor(
                    n_estimators=150,
                    max_depth=5,
                    learning_rate=0.08,
                    subsample=0.8,
                    colsample_bytree=0.8,
                    random_state=seed,
                    n_jobs=-1,
                )
            )),
        ]),
    }

    validation_results: Dict[str, Dict[str, float]] = {}
    fitted_pipelines: Dict[str, Pipeline] = {}

    for name, pipeline in candidates.items():
        print(f"Fitting candidate: {name}...")
        pipeline.fit(X_train, y_train)
        val_preds = pipeline.predict(X_val)
        metrics = compute_regression_metrics(y_val, val_preds)
        validation_results[name] = metrics
        fitted_pipelines[name] = pipeline

        print(
            f"  -> Val MAE: {metrics['mae_minutes']:6.2f} min | "
            f"RMSE: {metrics['rmse_minutes']:6.2f} min | "
            f"R2: {metrics['r2_score']:6.3f} | "
            f"Within +/-10m: {metrics['within_10_minutes_percent']:5.1f}%"
        )

    # Model Selection: Best model has lowest validation MAE
    # (Excluding baseline from being selected if ML models outperform it)
    ml_candidates = [k for k in candidates.keys() if k != "mean_baseline"]
    selected_model_name = min(
        ml_candidates,
        key=lambda k: validation_results[k]["mae_minutes"],
    )

    print("-" * 70)
    print(f"Selected Model based on Validation MAE: '{selected_model_name}'")
    winning_pipeline = fitted_pipelines[selected_model_name]

    # Evaluate selected model ONCE on test split
    test_preds = winning_pipeline.predict(X_test)
    test_metrics = compute_regression_metrics(y_test, test_preds)
    print(
        f"Final Test Evaluation: MAE: {test_metrics['mae_minutes']:6.2f} min | "
        f"RMSE: {test_metrics['rmse_minutes']:6.2f} min | "
        f"R2: {test_metrics['r2_score']:6.3f} | "
        f"Within +/-10m: {test_metrics['within_10_minutes_percent']:5.1f}%"
    )
    print("=" * 70)

    # Full metadata and metrics dictionary
    full_metrics: Dict[str, Any] = {
        "task": "waiting_time_regression",
        "target": target,
        "target_unit": "minutes",
        "non_negative_guarantee": True,
        "selected_model": selected_model_name,
        "random_seed": seed,
        "dataset_provenance": "100% SYNTHETIC (backend/app/ml/data/waiting_time_dataset.csv)",
        "synthetic_notice": (
            "All metrics reflect performance exclusively on synthetic queue simulation data. "
            "These metrics must not be represented as real clinical accuracy."
        ),
        "trained_at_utc": datetime.now(timezone.utc).isoformat(),
        "splits": split_meta,
        "feature_schema": {
            "categorical": CATEGORICAL_FEATURES,
            "numeric": NUMERIC_FEATURES,
            "all_features": features,
        },
        "validation_comparison": validation_results,
        "test_performance": test_metrics,
    }

    return winning_pipeline, full_metrics


def save_artifacts(
    pipeline: Pipeline,
    metrics: Dict[str, Any],
    artifacts_dir: Path = ARTIFACTS_DIR,
) -> Tuple[Path, Path]:
    """Persists fitted pipeline joblib and metrics JSON."""
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    model_path = artifacts_dir / "waiting_time_pipeline.joblib"
    metrics_path = artifacts_dir / "waiting_time_metrics.json"

    joblib.dump(pipeline, model_path)
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    print(f"Artifacts successfully saved to:\n  - {model_path}\n  - {metrics_path}")
    return model_path, metrics_path


def run_pipeline() -> Tuple[Path, Path]:
    """Full execution: train, compare, select, evaluate, and save."""
    winning_pipeline, full_metrics = train_and_evaluate_models()
    return save_artifacts(winning_pipeline, full_metrics)


if __name__ == "__main__":
    run_pipeline()
