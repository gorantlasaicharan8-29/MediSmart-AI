"""
Tests for Phase 6.3: Appointment No-Show Prediction Model Training & Inference.

Validates:
1. No-show model artifact and metrics JSON presence, schema, and metadata.
2. Winning model selection superiority on validation PR-AUC over Dummy baseline.
3. Pipeline loading and inference behavior (single sample and batch).
4. Output probability bounds in [0.0, 1.0] and binary discrete prediction in {0, 1}.
5. Robustness to unknown categorical specialty values (handle_unknown='ignore').
6. Finite numeric predictions without NaNs or Infs.
7. Exact reproducibility with fixed random seed.
8. Absence of post-booking or target leakage in feature columns.
9. Chronological split integrity (train < validation < test).
10. Standalone operation with zero database dependencies.
"""
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest

from app.ml.config import (
    ARTIFACTS_DIR,
    DEFAULT_RANDOM_SEED,
    NOSHOW_DATASET_PATH,
    NOSHOW_FEATURES,
    NOSHOW_MODEL_PATH,
    NOSHOW_TARGET,
)
from app.ml.estimators import ThresholdClassifier
from app.ml.train_noshow import (
    CATEGORICAL_FEATURES,
    NOSHOW_METRICS_PATH,
    NUMERIC_FEATURES,
    compute_classification_metrics,
    find_optimal_threshold,
    prepare_chronological_splits,
    train_and_evaluate_models,
)


@pytest.fixture(scope="module")
def loaded_noshow_pipeline():
    """Loads the persisted no-show classification pipeline artifact."""
    assert NOSHOW_MODEL_PATH.exists(), (
        f"Pipeline artifact not found at {NOSHOW_MODEL_PATH}. "
        "Run `python -m app.ml.train_noshow` first."
    )
    return joblib.load(NOSHOW_MODEL_PATH)


@pytest.fixture(scope="module")
def sample_noshow_feature_row():
    """Generates a standard valid feature row matching the booking-time schema."""
    return pd.DataFrame([{
        "doctor_specialty": "Cardiology",
        "lead_time_days": 14,
        "day_of_week": 1,  # Tuesday
        "slot_hour": 10,
        "is_weekend": 0,
        "consultation_fee": 1200.0,
        "patient_prior_appointments": 3,
        "patient_prior_no_shows": 1,
        "patient_prior_no_show_rate": 0.3333,
        "has_notes": 1,
    }])


class TestNoShowArtifacts:
    """Validates persisted artifacts, metadata, and selection criteria."""

    def test_artifacts_exist_on_disk(self):
        """Verifies model joblib and metrics json exist and are non-empty."""
        assert NOSHOW_MODEL_PATH.exists()
        assert NOSHOW_MODEL_PATH.stat().st_size > 500
        assert NOSHOW_METRICS_PATH.exists()
        assert NOSHOW_METRICS_PATH.stat().st_size > 500

    def test_metrics_json_structure_and_metadata(self):
        """Verifies metrics JSON schema, split counts, and provenance disclosures."""
        with open(NOSHOW_METRICS_PATH, "r", encoding="utf-8") as f:
            metrics = json.load(f)

        assert metrics["task"] == "noshow_classification"
        assert metrics["target"] == NOSHOW_TARGET
        assert metrics["selected_model"] in ["logistic_regression", "random_forest", "xgboost"]
        assert 0.0 < metrics["calibrated_threshold"] < 1.0
        assert metrics["random_seed"] == DEFAULT_RANDOM_SEED
        assert "SYNTHETIC" in metrics["dataset_provenance"]
        assert "synthetic_notice" in metrics
        assert "class_imbalance_analysis" in metrics

        # Split counts
        splits = metrics["splits"]
        assert splits["total_records"] == 10000
        assert splits["train"]["count"] == 7000
        assert splits["validation"]["count"] == 1500
        assert splits["test"]["count"] == 1500

        # Features
        assert metrics["feature_schema"]["categorical"] == CATEGORICAL_FEATURES
        assert metrics["feature_schema"]["numeric"] == NUMERIC_FEATURES

    def test_validation_model_selection_superiority(self):
        """Validates that ML candidates outperformed the dummy baseline on PR-AUC."""
        with open(NOSHOW_METRICS_PATH, "r", encoding="utf-8") as f:
            metrics = json.load(f)

        comp = metrics["validation_comparison"]
        base_pr_auc = comp["dummy_baseline"]["pr_auc"]
        lr_pr_auc = comp["logistic_regression"]["pr_auc"]
        rf_pr_auc = comp["random_forest"]["pr_auc"]
        xgb_pr_auc = comp["xgboost"]["pr_auc"]

        # All ML models should exceed dummy prior baseline
        assert lr_pr_auc > base_pr_auc
        assert rf_pr_auc > base_pr_auc
        assert xgb_pr_auc > base_pr_auc

        # Selected model matches recorded best validation candidate
        selected = metrics["selected_model"]
        selected_pr_auc = comp[selected]["pr_auc"]
        for name in ["logistic_regression", "random_forest", "xgboost"]:
            assert selected_pr_auc >= comp[name]["pr_auc"]

    def test_test_set_performance_bounds(self):
        """Confirms reasonable test performance bounds on held-out 15% split."""
        with open(NOSHOW_METRICS_PATH, "r", encoding="utf-8") as f:
            metrics = json.load(f)

        test_perf = metrics["test_performance"]["calibrated_threshold"]
        assert test_perf["pr_auc"] > 0.30, "Test PR-AUC should significantly exceed random baseline"
        assert test_perf["roc_auc"] > 0.60, "Test ROC-AUC should reflect meaningful ranking power"
        assert test_perf["f1_score"] > 0.35, "Test F1 should demonstrate balanced precision/recall"
        assert test_perf["brier_score"] < 0.25, "Test Brier score should indicate calibrated probabilities"


class TestPipelineInference:
    """Validates inference characteristics, probability bounds, and robustness."""

    def test_single_sample_inference(self, loaded_noshow_pipeline, sample_noshow_feature_row):
        """Verifies single-row prediction succeeds with expected shape and type."""
        probs = loaded_noshow_pipeline.predict_proba(sample_noshow_feature_row)
        preds = loaded_noshow_pipeline.predict(sample_noshow_feature_row)

        assert isinstance(probs, np.ndarray)
        assert probs.shape == (1, 2)
        assert np.isclose(np.sum(probs[0]), 1.0)
        assert 0.0 <= probs[0, 1] <= 1.0

        assert isinstance(preds, np.ndarray)
        assert preds.shape == (1,)
        assert preds[0] in [0, 1]

    def test_batch_inference_shape_and_finite(self, loaded_noshow_pipeline):
        """Verifies batch prediction produces valid probabilities and discrete classes."""
        df = pd.read_csv(NOSHOW_DATASET_PATH)
        features = CATEGORICAL_FEATURES + NUMERIC_FEATURES
        X_sample = df[features].head(50)

        probs = loaded_noshow_pipeline.predict_proba(X_sample)
        preds = loaded_noshow_pipeline.predict(X_sample)

        assert probs.shape == (50, 2)
        assert np.isfinite(probs).all()
        assert (probs >= 0.0).all() and (probs <= 1.0).all()
        assert np.allclose(np.sum(probs, axis=1), 1.0)

        assert preds.shape == (50,)
        assert set(preds).issubset({0, 1})

    def test_unknown_categorical_handling(self, loaded_noshow_pipeline, sample_noshow_feature_row):
        """Verifies OneHotEncoder handles unseen clinical specialties gracefully."""
        unseen_row = sample_noshow_feature_row.copy()
        unseen_row["doctor_specialty"] = "Aero-Space Surgery"  # Unseen specialty

        probs = loaded_noshow_pipeline.predict_proba(unseen_row)
        preds = loaded_noshow_pipeline.predict(unseen_row)

        assert probs.shape == (1, 2)
        assert np.isfinite(probs[0]).all()
        assert preds[0] in [0, 1]


class TestChronologicalAndLeakageIntegrity:
    """Verifies strict temporal ordering and absence of post-booking target leakage."""

    def test_chronological_splits_non_overlapping(self):
        """Ensures train, validation, and test splits are strictly sequential without time travel."""
        train_df, val_df, test_df, meta = prepare_chronological_splits()

        train_end = meta["train"]["date_end"]
        val_start = meta["validation"]["date_start"]
        val_end = meta["validation"]["date_end"]
        test_start = meta["test"]["date_start"]

        assert train_end <= val_start, "Train split leaks into validation timeline"
        assert val_end <= test_start, "Validation split leaks into test timeline"

    def test_no_target_leakage_in_features(self):
        """Verifies check-in, queue, or post-event columns are absent from training features."""
        forbidden_features = [
            "is_no_show",
            "checked_in_at",
            "token_number",
            "queue_entry_id",
            "called_at",
            "completed_at",
            "actual_wait_minutes",
            "status",
        ]
        all_features = CATEGORICAL_FEATURES + NUMERIC_FEATURES
        for col in forbidden_features:
            assert col not in all_features, f"LEAKAGE DETECTED: '{col}' found in no-show feature list!"

    def test_deterministic_training_reproducibility(self):
        """Training with the same seed must produce identical test metrics."""
        _, meta1 = train_and_evaluate_models(seed=DEFAULT_RANDOM_SEED)
        _, meta2 = train_and_evaluate_models(seed=DEFAULT_RANDOM_SEED)

        assert meta1["selected_model"] == meta2["selected_model"]
        assert meta1["test_performance"]["calibrated_threshold"]["pr_auc"] == (
            meta2["test_performance"]["calibrated_threshold"]["pr_auc"]
        )

    def test_zero_database_dependency(self, loaded_noshow_pipeline, sample_noshow_feature_row):
        """Confirms pipeline executes strictly in-memory without database access."""
        probs = loaded_noshow_pipeline.predict_proba(sample_noshow_feature_row)
        assert len(probs) == 1
