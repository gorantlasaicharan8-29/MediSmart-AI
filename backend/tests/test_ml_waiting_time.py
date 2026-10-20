"""
Tests for Phase 6.2: Waiting-Time Prediction Model Training & Inference.

Validates:
1. Model artifact and metrics JSON presence, schema, and metadata.
2. Winning model selection based on validation MAE.
3. Pipeline loading and inference behavior (single sample and batch).
4. Strictly non-negative waiting-time predictions (>= 0.0 min).
5. Robustness to unknown categorical specialty values (handle_unknown='ignore').
6. Finite numeric predictions without NaNs or Infs.
7. Exact reproducibility with fixed random seed.
8. Absence of target leakage in training/inference feature sets.
9. Standalone operation with zero database dependencies.
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
    WAITING_TIME_DATASET_PATH,
    WAITING_TIME_FEATURES,
    WAITING_TIME_MODEL_PATH,
    WAITING_TIME_TARGET,
)
from app.ml.estimators import NonNegativeRegressor
from app.ml.train_waiting_time import (
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    WAITING_TIME_METRICS_PATH,
    compute_regression_metrics,
    prepare_chronological_splits,
    train_and_evaluate_models,
)


@pytest.fixture(scope="module")
def loaded_pipeline():
    """Loads the persisted waiting-time pipeline artifact."""
    assert WAITING_TIME_MODEL_PATH.exists(), (
        f"Pipeline artifact not found at {WAITING_TIME_MODEL_PATH}. "
        "Run `python -m app.ml.train_waiting_time` first."
    )
    return joblib.load(WAITING_TIME_MODEL_PATH)


@pytest.fixture(scope="module")
def sample_feature_row():
    """Generates a standard valid feature row matching the inference schema."""
    return pd.DataFrame([{
        "doctor_specialty": "Cardiology",
        "doctor_experience_years": 15,
        "day_of_week": 2,  # Wednesday
        "slot_hour": 10,
        "slot_minute": 30,
        "arrival_lead_minutes": 10.0,
        "queue_position_at_checkin": 3,
        "patients_waiting_ahead": 2,
        "is_doctor_active_consultation": 1,
        "historical_avg_consultation_minutes": 18.0,
    }])


class TestWaitingTimeArtifacts:
    """Validates persisted artifacts, metadata, and selection criteria."""

    def test_artifacts_exist_on_disk(self):
        """Verifies model joblib and metrics json exist and are non-empty."""
        assert WAITING_TIME_MODEL_PATH.exists()
        assert WAITING_TIME_MODEL_PATH.stat().st_size > 1000  # Non-trivial size
        assert WAITING_TIME_METRICS_PATH.exists()
        assert WAITING_TIME_METRICS_PATH.stat().st_size > 200

    def test_metrics_json_structure_and_metadata(self):
        """Verifies metrics JSON schema and provenance disclosures."""
        with open(WAITING_TIME_METRICS_PATH, "r", encoding="utf-8") as f:
            metrics = json.load(f)

        assert metrics["task"] == "waiting_time_regression"
        assert metrics["target"] == WAITING_TIME_TARGET
        assert metrics["target_unit"] == "minutes"
        assert metrics["non_negative_guarantee"] is True
        assert metrics["selected_model"] in ["xgboost", "random_forest", "ridge_regression"]
        assert metrics["random_seed"] == DEFAULT_RANDOM_SEED
        assert "SYNTHETIC" in metrics["dataset_provenance"]
        assert "synthetic_notice" in metrics

        # Split counts
        splits = metrics["splits"]
        assert splits["total_records"] == 5000
        assert splits["train"]["count"] == 3500
        assert splits["validation"]["count"] == 750
        assert splits["test"]["count"] == 750

        # Features
        assert metrics["feature_schema"]["categorical"] == CATEGORICAL_FEATURES
        assert metrics["feature_schema"]["numeric"] == NUMERIC_FEATURES

    def test_validation_model_selection_superiority(self):
        """Validates that ML candidates outperformed the baseline on validation MAE."""
        with open(WAITING_TIME_METRICS_PATH, "r", encoding="utf-8") as f:
            metrics = json.load(f)

        comp = metrics["validation_comparison"]
        base_mae = comp["mean_baseline"]["mae_minutes"]
        ridge_mae = comp["ridge_regression"]["mae_minutes"]
        rf_mae = comp["random_forest"]["mae_minutes"]
        xgb_mae = comp["xgboost"]["mae_minutes"]

        # All ML candidates beat mean baseline substantially
        assert ridge_mae < base_mae
        assert rf_mae < ridge_mae
        assert xgb_mae < ridge_mae

        # Selected model matches recorded best validation candidate
        selected = metrics["selected_model"]
        selected_val_mae = comp[selected]["mae_minutes"]
        for name, res in comp.items():
            if name != "mean_baseline":
                assert selected_val_mae <= res["mae_minutes"]

    def test_test_set_performance_bounds(self):
        """Confirms reasonable test performance bounds on held-out 15% split."""
        with open(WAITING_TIME_METRICS_PATH, "r", encoding="utf-8") as f:
            metrics = json.load(f)

        test_perf = metrics["test_performance"]
        assert test_perf["mae_minutes"] < 12.0, "Test MAE should be well within clinic tolerance"
        assert test_perf["r2_score"] > 0.90, "Test R2 should reflect high explained variance"
        assert test_perf["within_10_minutes_percent"] > 65.0, "Expected >65% within 10 min tolerance"


class TestPipelineInference:
    """Validates inference characteristics and output guarantees."""

    def test_single_sample_inference(self, loaded_pipeline, sample_feature_row):
        """Verifies single-row prediction succeeds with expected shape and type."""
        preds = loaded_pipeline.predict(sample_feature_row)
        assert isinstance(preds, np.ndarray)
        assert preds.shape == (1,)
        assert np.issubdtype(preds.dtype, np.floating)
        assert np.isfinite(preds[0])
        assert preds[0] >= 0.0

    def test_batch_inference_shape_and_finite(self, loaded_pipeline):
        """Verifies batch prediction produces non-null, finite outputs."""
        df = pd.read_csv(WAITING_TIME_DATASET_PATH)
        features = CATEGORICAL_FEATURES + NUMERIC_FEATURES
        X_sample = df[features].head(50)

        preds = loaded_pipeline.predict(X_sample)
        assert preds.shape == (50,)
        assert np.isfinite(preds).all()
        assert (preds >= 0.0).all()

    def test_non_negative_prediction_guarantee(self, loaded_pipeline):
        """
        Tests that extreme inputs (e.g. 0 patients ahead, early arrival, rapid consultation)
        never yield negative wait times.
        """
        edge_cases = pd.DataFrame([
            {
                "doctor_specialty": "Dermatology",
                "doctor_experience_years": 40,
                "day_of_week": 0,
                "slot_hour": 9,
                "slot_minute": 0,
                "arrival_lead_minutes": 30.0,
                "queue_position_at_checkin": 1,
                "patients_waiting_ahead": 0,
                "is_doctor_active_consultation": 0,
                "historical_avg_consultation_minutes": 8.0,
            },
            {
                "doctor_specialty": "General Medicine",
                "doctor_experience_years": 30,
                "day_of_week": 1,
                "slot_hour": 9,
                "slot_minute": 0,
                "arrival_lead_minutes": 45.0,
                "queue_position_at_checkin": 1,
                "patients_waiting_ahead": 0,
                "is_doctor_active_consultation": 0,
                "historical_avg_consultation_minutes": 6.0,
            },
        ])
        preds = loaded_pipeline.predict(edge_cases)
        assert (preds >= 0.0).all(), "Predictions must be strictly non-negative"

    def test_unknown_categorical_handling(self, loaded_pipeline, sample_feature_row):
        """Verifies OneHotEncoder handles unseen clinical specialties gracefully."""
        unseen_row = sample_feature_row.copy()
        unseen_row["doctor_specialty"] = "Aviation Medicine"  # Not in training specialties

        # Should predict without throwing ValueError
        preds = loaded_pipeline.predict(unseen_row)
        assert preds.shape == (1,)
        assert np.isfinite(preds[0])
        assert preds[0] >= 0.0


class TestReproducibilityAndLeakage:
    """Verifies deterministic training and absence of post-event target leakage."""

    def test_deterministic_training_reproducibility(self):
        """Training with the same seed must produce identical test performance."""
        _, meta1 = train_and_evaluate_models(seed=DEFAULT_RANDOM_SEED)
        _, meta2 = train_and_evaluate_models(seed=DEFAULT_RANDOM_SEED)

        assert meta1["selected_model"] == meta2["selected_model"]
        assert meta1["test_performance"]["mae_minutes"] == meta2["test_performance"]["mae_minutes"]
        assert meta1["test_performance"]["r2_score"] == meta2["test_performance"]["r2_score"]

    def test_no_target_leakage_in_feature_columns(self):
        """Verifies no post-event or target columns are in the training feature list."""
        forbidden_features = [
            "actual_wait_minutes",
            "called_at",
            "completed_at",
            "actual_consultation_minutes",
            "notes",
            "diagnosis",
            "prescription",
            "status",
        ]
        all_features = CATEGORICAL_FEATURES + NUMERIC_FEATURES
        for col in forbidden_features:
            assert col not in all_features, f"LEAKAGE DETECTED: '{col}' present in features!"

    def test_zero_database_dependency(self, loaded_pipeline, sample_feature_row):
        """Confirms pipeline executes strictly in-memory without database access."""
        # Standard predict without any database mocks or connections
        preds = loaded_pipeline.predict(sample_feature_row)
        assert len(preds) == 1
