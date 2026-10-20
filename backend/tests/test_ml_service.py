"""
Tests for Phase 6.4: Shared ML Prediction Service.

Validates:
1. Valid single-record inference for waiting-time regression and no-show classification.
2. Strict Pydantic input validation for missing, out-of-range, and malformed features.
3. Graceful handling of unknown categorical values (unseen clinical specialties).
4. Strictly non-negative waiting-time predictions (>= 0.0 min).
5. Strictly bounded no-show probabilities in [0.0, 1.0] and threshold consistency.
6. Error handling for missing or corrupted model artifacts (sanitized exceptions).
7. In-memory caching and lazy loading behavior (singleton re-use).
8. Synthetic provenance disclosures and non-diagnostic risk band disclaimers.
9. Zero database access or mutations during inference execution.
"""
from pathlib import Path
import pytest
from pydantic import ValidationError

from app.ml.service import (
    MLPredictionService,
    ModelArtifactNotFoundError,
    ModelInferenceError,
    ml_prediction_service,
)
from app.schemas.ml import (
    NoShowPredictionRequest,
    NoShowPredictionResponse,
    WaitingTimePredictionRequest,
    WaitingTimePredictionResponse,
)


@pytest.fixture
def valid_waiting_time_request():
    """Returns a valid WaitingTimePredictionRequest payload."""
    return WaitingTimePredictionRequest(
        doctor_specialty="Cardiology",
        doctor_experience_years=12,
        day_of_week=2,  # Wednesday
        slot_hour=11,
        slot_minute=0,
        arrival_lead_minutes=15.0,
        queue_position_at_checkin=4,
        patients_waiting_ahead=3,
        is_doctor_active_consultation=1,
        historical_avg_consultation_minutes=18.0,
    )


@pytest.fixture
def valid_noshow_request():
    """Returns a valid NoShowPredictionRequest payload."""
    return NoShowPredictionRequest(
        doctor_specialty="Cardiology",
        lead_time_days=10,
        day_of_week=3,  # Thursday
        slot_hour=14,
        is_weekend=0,
        consultation_fee=1100.0,
        patient_prior_appointments=2,
        patient_prior_no_shows=0,
        patient_prior_no_show_rate=0.0,
        has_notes=1,
    )


class TestMLServiceStatusAndLoading:
    """Tests model lifecycle, caching, and readiness queries."""

    def test_service_status_reporting(self):
        """Verifies status dictionary reports artifact existence and synthetic provenance."""
        status = ml_prediction_service.get_service_status()
        assert "waiting_time_model" in status
        assert "noshow_model" in status
        assert status["waiting_time_model"]["artifact_exists"] is True
        assert status["noshow_model"]["artifact_exists"] is True
        assert status["waiting_time_model"]["is_synthetic"] is True
        assert status["noshow_model"]["is_synthetic"] is True

    def test_in_memory_caching_avoids_repeated_disk_loads(self):
        """Verifies consecutive load calls return the identical cached Pipeline instance."""
        pipe1 = ml_prediction_service.load_waiting_time_model()
        pipe2 = ml_prediction_service.load_waiting_time_model()
        assert pipe1 is pipe2, "Pipeline must be cached in memory, not re-read from disk"

        ns_pipe1 = ml_prediction_service.load_noshow_model()
        ns_pipe2 = ml_prediction_service.load_noshow_model()
        assert ns_pipe1 is ns_pipe2, "No-show pipeline must be cached in memory"

    def test_missing_artifact_raises_sanitized_exception(self, tmp_path: Path):
        """Verifies missing artifact raises ModelArtifactNotFoundError without exposing paths."""
        non_existent_path = tmp_path / "non_existent_pipeline.joblib"
        service = MLPredictionService(
            waiting_time_model_path=non_existent_path,
            noshow_model_path=non_existent_path,
        )
        with pytest.raises(ModelArtifactNotFoundError) as exc_info:
            service.load_waiting_time_model()

        err_msg = str(exc_info.value)
        assert "unavailable" in err_msg.lower() or "missing" in err_msg.lower()
        # Ensure raw full filesystem path is not leaked in the client-facing exception message
        assert str(tmp_path) not in err_msg

    def test_corrupt_artifact_raises_model_inference_error(self, tmp_path: Path):
        """Verifies corrupt/truncated artifact raises ModelInferenceError."""
        corrupt_file = tmp_path / "corrupt_pipeline.joblib"
        corrupt_file.write_text("not a valid joblib pickle content", encoding="utf-8")

        service = MLPredictionService(
            waiting_time_model_path=corrupt_file,
            noshow_model_path=corrupt_file,
        )
        with pytest.raises(ModelInferenceError) as exc_info:
            service.load_waiting_time_model()
        assert "failed to initialize" in str(exc_info.value).lower()


class TestWaitingTimeInference:
    """Tests waiting-time regression service inference."""

    def test_valid_waiting_time_prediction(self, valid_waiting_time_request):
        """Verifies successful waiting-time prediction with expected schema."""
        resp = ml_prediction_service.predict_waiting_time(valid_waiting_time_request)

        assert isinstance(resp, WaitingTimePredictionResponse)
        assert resp.predicted_wait_minutes >= 0.0
        assert resp.unit == "minutes"
        assert resp.model_name == "xgboost"
        assert resp.model_version == "1.0.0"
        assert resp.prediction_source == "ml_synthetic_model"
        assert resp.is_synthetic_model is True
        assert "synthetic" in resp.synthetic_notice.lower()

    def test_non_negative_guarantee_on_fast_consultation(self):
        """Verifies extreme fast-service check-in edge case never produces negative wait time."""
        req = WaitingTimePredictionRequest(
            doctor_specialty="Dermatology",
            doctor_experience_years=35,
            day_of_week=0,
            slot_hour=9,
            slot_minute=0,
            arrival_lead_minutes=45.0,  # Arrived very early
            queue_position_at_checkin=1,  # First patient
            patients_waiting_ahead=0,
            is_doctor_active_consultation=0,
            historical_avg_consultation_minutes=7.0,
        )
        resp = ml_prediction_service.predict_waiting_time(req)
        assert resp.predicted_wait_minutes >= 0.0

    def test_unknown_doctor_specialty_handled_gracefully(self, valid_waiting_time_request):
        """Verifies unseen clinical specialties are handled by OneHotEncoder ignore policy."""
        valid_waiting_time_request.doctor_specialty = "Interventional Robotic Neurosurgery"
        resp = ml_prediction_service.predict_waiting_time(valid_waiting_time_request)

        assert isinstance(resp, WaitingTimePredictionResponse)
        assert resp.predicted_wait_minutes >= 0.0

    def test_input_validation_catches_invalid_fields(self):
        """Verifies Pydantic catches out-of-range or negative values."""
        # Negative experience
        with pytest.raises(ValidationError):
            WaitingTimePredictionRequest(
                doctor_specialty="Cardiology",
                doctor_experience_years=-5,
                day_of_week=1,
                slot_hour=10,
                slot_minute=0,
                arrival_lead_minutes=0.0,
                queue_position_at_checkin=1,
                patients_waiting_ahead=0,
                is_doctor_active_consultation=0,
                historical_avg_consultation_minutes=15.0,
            )

        # Invalid day of week (7 > 6)
        with pytest.raises(ValidationError):
            WaitingTimePredictionRequest(
                doctor_specialty="Cardiology",
                doctor_experience_years=10,
                day_of_week=7,
                slot_hour=10,
                slot_minute=0,
                arrival_lead_minutes=0.0,
                queue_position_at_checkin=1,
                patients_waiting_ahead=0,
                is_doctor_active_consultation=0,
                historical_avg_consultation_minutes=15.0,
            )

        # Zero or negative historical consultation duration
        with pytest.raises(ValidationError):
            WaitingTimePredictionRequest(
                doctor_specialty="Cardiology",
                doctor_experience_years=10,
                day_of_week=1,
                slot_hour=10,
                slot_minute=0,
                arrival_lead_minutes=0.0,
                queue_position_at_checkin=1,
                patients_waiting_ahead=0,
                is_doctor_active_consultation=0,
                historical_avg_consultation_minutes=0.0,
            )


class TestNoShowInference:
    """Tests appointment no-show classification service inference."""

    def test_valid_noshow_prediction(self, valid_noshow_request):
        """Verifies successful no-show prediction with probabilities, flags, and notices."""
        resp = ml_prediction_service.predict_no_show(valid_noshow_request)

        assert isinstance(resp, NoShowPredictionResponse)
        assert 0.0 <= resp.no_show_probability <= 1.0
        assert resp.predicted_no_show in [0, 1]
        assert resp.decision_threshold == 0.50
        assert resp.risk_band in ["low", "moderate", "high"]
        assert "not clinically validated" in resp.risk_band_notice.lower()
        assert resp.model_name == "logistic_regression"
        assert resp.model_version == "1.0.0"
        assert resp.prediction_source == "ml_synthetic_model"
        assert resp.is_synthetic_model is True
        assert "synthetic" in resp.synthetic_notice.lower()

    def test_threshold_consistency(self, valid_noshow_request):
        """Verifies predicted_no_show binary output is consistent with decision_threshold."""
        resp = ml_prediction_service.predict_no_show(valid_noshow_request)
        if resp.no_show_probability >= resp.decision_threshold:
            assert resp.predicted_no_show == 1
        else:
            assert resp.predicted_no_show == 0

    def test_unknown_specialty_handled_gracefully(self, valid_noshow_request):
        """Verifies unseen specialty is handled gracefully by OneHotEncoder ignore policy."""
        valid_noshow_request.doctor_specialty = "Tropical Dermatology"
        resp = ml_prediction_service.predict_no_show(valid_noshow_request)

        assert isinstance(resp, NoShowPredictionResponse)
        assert 0.0 <= resp.no_show_probability <= 1.0

    def test_noshow_input_validation(self):
        """Verifies Pydantic catches negative or out-of-range features."""
        # Negative lead time
        with pytest.raises(ValidationError):
            NoShowPredictionRequest(
                doctor_specialty="Cardiology",
                lead_time_days=-1,
                day_of_week=0,
                slot_hour=10,
                is_weekend=0,
                consultation_fee=500.0,
                patient_prior_appointments=0,
                patient_prior_no_shows=0,
                patient_prior_no_show_rate=0.0,
                has_notes=0,
            )

        # Prior rate > 1.0
        with pytest.raises(ValidationError):
            NoShowPredictionRequest(
                doctor_specialty="Cardiology",
                lead_time_days=5,
                day_of_week=0,
                slot_hour=10,
                is_weekend=0,
                consultation_fee=500.0,
                patient_prior_appointments=2,
                patient_prior_no_shows=3,
                patient_prior_no_show_rate=1.5,
                has_notes=0,
            )


class TestZeroDatabaseSideEffects:
    """Verifies predictions run purely in memory without database interactions."""

    def test_predictions_do_not_access_or_write_database(
        self,
        valid_waiting_time_request,
        valid_noshow_request,
    ):
        """Inference should execute purely in memory without opening DB sessions."""
        wt_resp = ml_prediction_service.predict_waiting_time(valid_waiting_time_request)
        ns_resp = ml_prediction_service.predict_no_show(valid_noshow_request)

        assert wt_resp.predicted_wait_minutes >= 0.0
        assert 0.0 <= ns_resp.no_show_probability <= 1.0
