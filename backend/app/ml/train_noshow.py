"""
Appointment No-Show Prediction Model Training & Evaluation for MediSmart.

Chronological 70/15/15 train/validation/test split on synthetic appointment dataset.
Evaluates:
1. Dummy Classifier (Prior Baseline)
2. Logistic Regression (Class-Weighted)
3. Random Forest Classifier (Class-Weighted)
4. XGBoost Classifier (Scale-Pos-Weighted)

Selects winning model based strictly on validation split PR-AUC & F1-score.
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
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBClassifier

from app.ml.config import (
    ARTIFACTS_DIR,
    DEFAULT_RANDOM_SEED,
    NOSHOW_DATASET_PATH,
    NOSHOW_FEATURES,
    NOSHOW_MODEL_PATH,
    NOSHOW_TARGET,
)
from app.ml.estimators import ThresholdClassifier

logger = logging.getLogger("medismart.ml.noshow")

NOSHOW_METRICS_PATH = ARTIFACTS_DIR / "noshow_metrics.json"

CATEGORICAL_FEATURES = ["doctor_specialty"]
NUMERIC_FEATURES = [
    "lead_time_days",
    "day_of_week",
    "slot_hour",
    "is_weekend",
    "consultation_fee",
    "patient_prior_appointments",
    "patient_prior_no_shows",
    "patient_prior_no_show_rate",
    "has_notes",
]


def compute_classification_metrics(
    y_true: np.ndarray,
    probs: np.ndarray,
    threshold: float = 0.5,
) -> Dict[str, Any]:
    """
    Computes PR-AUC, ROC-AUC, Brier score, Precision, Recall, F1, and Confusion Matrix.
    """
    preds = (probs >= threshold).astype(int)
    pr_auc = float(average_precision_score(y_true, probs))
    roc_auc = float(roc_auc_score(y_true, probs))
    brier = float(brier_score_loss(y_true, probs))
    prec = float(precision_score(y_true, preds, zero_division=0))
    rec = float(recall_score(y_true, preds, zero_division=0))
    f1 = float(f1_score(y_true, preds, zero_division=0))
    cm = confusion_matrix(y_true, preds).tolist()
    prevalence = float(np.mean(y_true))

    return {
        "pr_auc": round(pr_auc, 4),
        "roc_auc": round(roc_auc, 4),
        "brier_score": round(brier, 4),
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1_score": round(f1, 4),
        "threshold": round(threshold, 3),
        "confusion_matrix": cm,
        "prevalence": round(prevalence, 4),
    }


def find_optimal_threshold(
    y_true: np.ndarray,
    probs: np.ndarray,
    thresholds: np.ndarray = np.linspace(0.20, 0.80, 61),
) -> Tuple[float, float]:
    """
    Finds the decision threshold maximizing F1 score on the validation split.
    Guarantees threshold tuning does not touch test labels.
    """
    best_t = 0.5
    best_f1 = -1.0
    for t in thresholds:
        preds = (probs >= t).astype(int)
        score = f1_score(y_true, preds, zero_division=0)
        if score > best_f1:
            best_f1 = score
            best_t = float(t)
    return best_t, float(best_f1)


def prepare_chronological_splits(
    dataset_path: Path = NOSHOW_DATASET_PATH,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    """
    Loads dataset, verifies synthetic provenance, sorts chronologically by appointment_date,
    and partitions into 70% train (7,000), 15% validation (1,500), and 15% test (1,500).
    """
    df = pd.read_csv(dataset_path)

    # 1. Provenance check
    assert "is_synthetic" in df.columns and df["is_synthetic"].all(), (
        "Dataset must be explicitly labeled synthetic on all records"
    )

    # 2. Chronological sort (stable sort to preserve intra-day causality)
    df = df.sort_values("appointment_date", kind="mergesort").reset_index(drop=True)

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
            "no_show_prevalence": round(float(train_df["is_no_show"].mean()), 4),
            "date_start": str(train_df["appointment_date"].min()),
            "date_end": str(train_df["appointment_date"].max()),
        },
        "validation": {
            "count": len(val_df),
            "no_show_prevalence": round(float(val_df["is_no_show"].mean()), 4),
            "date_start": str(val_df["appointment_date"].min()),
            "date_end": str(val_df["appointment_date"].max()),
        },
        "test": {
            "count": len(test_df),
            "no_show_prevalence": round(float(test_df["is_no_show"].mean()), 4),
            "date_start": str(test_df["appointment_date"].min()),
            "date_end": str(test_df["appointment_date"].max()),
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
    dataset_path: Path = NOSHOW_DATASET_PATH,
    seed: int = DEFAULT_RANDOM_SEED,
) -> Tuple[Pipeline, Dict[str, Any]]:
    """
    Trains candidate classification models, evaluates on validation data,
    selects winning model, evaluates on test data once, and returns the pipeline and metrics.
    """
    train_df, val_df, test_df, split_meta = prepare_chronological_splits(dataset_path)

    features = CATEGORICAL_FEATURES + NUMERIC_FEATURES
    target = NOSHOW_TARGET

    X_train, y_train = train_df[features], train_df[target].values
    X_val, y_val = val_df[features], val_df[target].values
    X_test, y_test = test_df[features], test_df[target].values

    # Imbalance scale factor for XGBoost
    n_pos = int(np.sum(y_train == 1))
    n_neg = int(np.sum(y_train == 0))
    scale_pos_weight = float(n_neg / n_pos)

    print("=" * 75)
    print("MEDISMART APPOINTMENT NO-SHOW PREDICTION: MODEL TRAINING & COMPARISON")
    print("=" * 75)
    print(f"Dataset: {dataset_path.name} ({len(train_df) + len(val_df) + len(test_df)} records)")
    print(f"Train Split:      {split_meta['train']['count']} rows ({split_meta['train']['date_start']} to {split_meta['train']['date_end']}) | Prevalence: {split_meta['train']['no_show_prevalence']:.1%}")
    print(f"Validation Split: {split_meta['validation']['count']} rows ({split_meta['validation']['date_start']} to {split_meta['validation']['date_end']}) | Prevalence: {split_meta['validation']['no_show_prevalence']:.1%}")
    print(f"Test Split:       {split_meta['test']['count']} rows ({split_meta['test']['date_start']} to {split_meta['test']['date_end']}) | Prevalence: {split_meta['test']['no_show_prevalence']:.1%}")
    print("-" * 75)

    candidates = {
        "dummy_baseline": Pipeline([
            ("clf", DummyClassifier(strategy="prior")),
        ]),
        "logistic_regression": Pipeline([
            ("preprocessor", build_preprocessor()),
            ("clf", LogisticRegression(class_weight="balanced", max_iter=1000, random_state=seed)),
        ]),
        "random_forest": Pipeline([
            ("preprocessor", build_preprocessor()),
            ("clf", RandomForestClassifier(n_estimators=100, max_depth=8, class_weight="balanced", random_state=seed, n_jobs=-1)),
        ]),
        "xgboost": Pipeline([
            ("preprocessor", build_preprocessor()),
            ("clf", XGBClassifier(
                n_estimators=120,
                max_depth=4,
                learning_rate=0.08,
                scale_pos_weight=scale_pos_weight,
                random_state=seed,
                eval_metric="logloss",
                n_jobs=-1,
            )),
        ]),
    }

    validation_results: Dict[str, Any] = {}
    fitted_pipelines: Dict[str, Pipeline] = {}
    val_probs_dict: Dict[str, np.ndarray] = {}

    for name, pipeline in candidates.items():
        print(f"Fitting candidate: {name}...")
        pipeline.fit(X_train, y_train)
        probs = pipeline.predict_proba(X_val)[:, 1]
        val_probs_dict[name] = probs
        fitted_pipelines[name] = pipeline

        # Standard threshold 0.5 metrics
        std_metrics = compute_classification_metrics(y_val, probs, threshold=0.5)
        # Optimal threshold on validation set
        opt_thresh, opt_f1 = find_optimal_threshold(y_val, probs)
        opt_metrics = compute_classification_metrics(y_val, probs, threshold=opt_thresh)

        validation_results[name] = {
            "standard_threshold_0.5": std_metrics,
            "optimal_threshold_tuning": {
                "optimal_threshold": opt_thresh,
                "metrics_at_optimal": opt_metrics,
            },
            "pr_auc": std_metrics["pr_auc"],
            "roc_auc": std_metrics["roc_auc"],
            "brier_score": std_metrics["brier_score"],
        }

        print(
            f"  -> PR-AUC: {std_metrics['pr_auc']:.4f} | ROC-AUC: {std_metrics['roc_auc']:.4f} | "
            f"Brier: {std_metrics['brier_score']:.4f} | F1: {std_metrics['f1_score']:.4f} | "
            f"Prec: {std_metrics['precision']:.4f} | Rec: {std_metrics['recall']:.4f}"
        )

    # Model Selection: Best non-dummy model based on Validation PR-AUC and F1-score
    ml_candidates = [k for k in candidates.keys() if k != "dummy_baseline"]
    selected_model_name = max(
        ml_candidates,
        key=lambda k: validation_results[k]["pr_auc"],
    )

    print("-" * 75)
    print(f"Selected Model based on Validation PR-AUC: '{selected_model_name}'")
    base_winning_pipe = fitted_pipelines[selected_model_name]
    winning_val_thresh = validation_results[selected_model_name]["optimal_threshold_tuning"]["optimal_threshold"]
    print(f"Optimal decision threshold calibrated on Validation split: {winning_val_thresh:.2f}")

    # Wrap winning pipeline with ThresholdClassifier so predict() enforces calibrated threshold
    # Note: Preprocessor + Base Classifier inside ThresholdClassifier
    winning_pipeline = Pipeline([
        ("preprocessor", base_winning_pipe.named_steps["preprocessor"]),
        ("clf", ThresholdClassifier(
            classifier=base_winning_pipe.named_steps["clf"],
            threshold=winning_val_thresh,
        )),
    ])
    # Refit outer threshold wrapper with training data
    winning_pipeline.fit(X_train, y_train)

    # Evaluate winning pipeline ONCE on held-out test split
    test_probs = winning_pipeline.predict_proba(X_test)[:, 1]
    test_metrics_std = compute_classification_metrics(y_test, test_probs, threshold=0.5)
    test_metrics_calibrated = compute_classification_metrics(y_test, test_probs, threshold=winning_val_thresh)

    print("-" * 75)
    print("FINAL TEST EVALUATION (Held-out Test Split - Evaluated Once):")
    print(
        f"  [Standard T=0.50] PR-AUC: {test_metrics_std['pr_auc']:.4f} | ROC-AUC: {test_metrics_std['roc_auc']:.4f} | "
        f"Brier: {test_metrics_std['brier_score']:.4f} | F1: {test_metrics_std['f1_score']:.4f} | "
        f"Prec: {test_metrics_std['precision']:.4f} | Rec: {test_metrics_std['recall']:.4f}"
    )
    print(
        f"  [Tuned T={winning_val_thresh:.2f}]  PR-AUC: {test_metrics_calibrated['pr_auc']:.4f} | ROC-AUC: {test_metrics_calibrated['roc_auc']:.4f} | "
        f"Brier: {test_metrics_calibrated['brier_score']:.4f} | F1: {test_metrics_calibrated['f1_score']:.4f} | "
        f"Prec: {test_metrics_calibrated['precision']:.4f} | Rec: {test_metrics_calibrated['recall']:.4f}"
    )
    print("=" * 75)

    full_metrics: Dict[str, Any] = {
        "task": "noshow_classification",
        "target": target,
        "selected_model": selected_model_name,
        "calibrated_threshold": winning_val_thresh,
        "random_seed": seed,
        "dataset_provenance": "100% SYNTHETIC (backend/app/ml/data/noshow_dataset.csv)",
        "synthetic_notice": (
            "All metrics reflect performance exclusively on synthetic appointment records. "
            "These metrics must not be represented as real clinical accuracy."
        ),
        "trained_at_utc": datetime.now(timezone.utc).isoformat(),
        "splits": split_meta,
        "feature_schema": {
            "categorical": CATEGORICAL_FEATURES,
            "numeric": NUMERIC_FEATURES,
            "all_features": features,
        },
        "class_imbalance_analysis": {
            "train_prevalence": split_meta["train"]["no_show_prevalence"],
            "validation_prevalence": split_meta["validation"]["no_show_prevalence"],
            "test_prevalence": split_meta["test"]["no_show_prevalence"],
            "scale_pos_weight": round(scale_pos_weight, 2),
            "explanation": (
                "With ~23% no-show prevalence, standard accuracy is misleading because predicting all zeros "
                "yields ~77% accuracy with 0 recall. PR-AUC and F1-score evaluate true positive recovery "
                "under clinical resource constraints."
            ),
        },
        "validation_comparison": validation_results,
        "test_performance": {
            "standard_threshold_0.5": test_metrics_std,
            "calibrated_threshold": test_metrics_calibrated,
        },
    }

    return winning_pipeline, full_metrics


def save_artifacts(
    pipeline: Pipeline,
    metrics: Dict[str, Any],
    artifacts_dir: Path = ARTIFACTS_DIR,
) -> Tuple[Path, Path]:
    """Persists fitted no-show pipeline joblib and metrics JSON."""
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    model_path = artifacts_dir / "noshow_pipeline.joblib"
    metrics_path = artifacts_dir / "noshow_metrics.json"

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
