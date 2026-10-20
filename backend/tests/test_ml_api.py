"""
Tests for Phase 6.5: ML Prediction API Endpoints.

Validates:
1. Authentication requirement: unauthenticated requests return 401 Unauthorized.
2. Successful waiting-time prediction (POST /api/v1/predictions/waiting-time).
3. Successful no-show prediction (POST /api/v1/predictions/no-show).
4. Prediction service status check (GET /api/v1/predictions/status).
5. Strict request body validation returning 422 for malformed/out-of-range inputs.
6. Unknown clinical specialty values handled gracefully (200 OK).
7. Missing model artifact returns sanitized 503 Service Unavailable (zero path leaks).
8. Inference execution failure returns sanitized 500 Internal Server Error (zero stack trace leaks).
9. Provenance transparency: synthetic disclosures on all responses.
10. Non-diagnostic risk band disclaimer present on no-show response.
11. Zero database side-effects (zero records created/updated/deleted).
"""
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import delete, func, select

from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token
from app.models.appointment import Appointment
from app.models.queue import QueueEntry
from app.models.user import User
from app.services.ml_prediction import (
    ModelArtifactNotFoundError,
    ModelInferenceError,
    ml_prediction_service,
)


@pytest.fixture(autouse=True)
async def cleanup_test_ml_users():
    """Cleanup fixture for test users created in ML API test suite."""
    yield
    async with AsyncSessionLocal() as session:
        await session.execute(delete(User).where(User.email.like("test_ml_api_%")))
        await session.commit()


async def create_auth_user(role: str = "patient") -> tuple[uuid.UUID, dict]:
    """Helper to create an active test user in test DB and return (user_id, headers)."""
    user_id = uuid.uuid4()
    email = f"test_ml_api_{role}_{uuid.uuid4().hex[:6]}@example.com"
    async with AsyncSessionLocal() as session:
        user = User(
            id=user_id,
            email=email,
            hashed_password="$argon2id$v=19$m=65536,t=2,p=1$fakehashfakehashfakehashfakehash",
            full_name=f"Test {role.title()}",
            role=role,
            is_active=True,
        )
        session.add(user)
        await session.commit()

    token = create_access_token(user_id=user_id, role=role)
    return user_id, {"Authorization": f"Bearer {token}"}


@pytest.fixture
def valid_waiting_time_payload():
    return {
        "doctor_specialty": "Cardiology",
        "doctor_experience_years": 14,
        "day_of_week": 2,
        "slot_hour": 10,
        "slot_minute": 30,
        "arrival_lead_minutes": 10.0,
        "queue_position_at_checkin": 3,
        "patients_waiting_ahead": 2,
        "is_doctor_active_consultation": 1,
        "historical_avg_consultation_minutes": 18.0,
    }


@pytest.fixture
def valid_noshow_payload():
    return {
        "doctor_specialty": "Cardiology",
        "lead_time_days": 12,
        "day_of_week": 1,
        "slot_hour": 11,
        "is_weekend": 0,
        "consultation_fee": 1200.0,
        "patient_prior_appointments": 2,
        "patient_prior_no_shows": 0,
        "patient_prior_no_show_rate": 0.0,
        "has_notes": 1,
    }


class TestPredictionEndpointsAuthentication:
    """Verifies that all prediction endpoints strictly require active authentication."""

    async def test_waiting_time_requires_auth(self, client: AsyncClient, valid_waiting_time_payload):
        """Unauthenticated POST /api/v1/predictions/waiting-time returns 401."""
        response = await client.post("/api/v1/predictions/waiting-time", json=valid_waiting_time_payload)
        assert response.status_code == 401
        assert "authentication required" in response.json()["detail"].lower()

    async def test_noshow_requires_auth(self, client: AsyncClient, valid_noshow_payload):
        """Unauthenticated POST /api/v1/predictions/no-show returns 401."""
        response = await client.post("/api/v1/predictions/no-show", json=valid_noshow_payload)
        assert response.status_code == 401
        assert "authentication required" in response.json()["detail"].lower()

    async def test_status_requires_auth(self, client: AsyncClient):
        """Unauthenticated GET /api/v1/predictions/status returns 401."""
        response = await client.get("/api/v1/predictions/status")
        assert response.status_code == 401


class TestPredictionEndpointsInference:
    """Verifies successful predictions and structured response models."""

    async def test_successful_waiting_time_prediction(
        self, client: AsyncClient, valid_waiting_time_payload
    ):
        """Authenticated waiting-time prediction returns 200 and valid schema."""
        _, headers = await create_auth_user()
        response = await client.post(
            "/api/v1/predictions/waiting-time",
            json=valid_waiting_time_payload,
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "predicted_wait_minutes" in data
        assert data["predicted_wait_minutes"] >= 0.0
        assert data["unit"] == "minutes"
        assert data["model_name"] == "xgboost"
        assert data["prediction_source"] == "ml_synthetic_model"
        assert data["is_synthetic_model"] is True
        assert "synthetic" in data["synthetic_notice"].lower()

    async def test_successful_noshow_prediction(
        self, client: AsyncClient, valid_noshow_payload
    ):
        """Authenticated no-show prediction returns 200, bounded probability, and risk band."""
        _, headers = await create_auth_user()
        response = await client.post(
            "/api/v1/predictions/no-show",
            json=valid_noshow_payload,
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert 0.0 <= data["no_show_probability"] <= 1.0
        assert data["predicted_no_show"] in [0, 1]
        assert data["decision_threshold"] == 0.50
        assert data["risk_band"] in ["low", "moderate", "high"]
        assert "not clinically validated" in data["risk_band_notice"].lower()
        assert data["model_name"] == "logistic_regression"
        assert data["prediction_source"] == "ml_synthetic_model"
        assert data["is_synthetic_model"] is True
        assert "synthetic" in data["synthetic_notice"].lower()

    async def test_unknown_specialty_handled_gracefully(
        self, client: AsyncClient, valid_waiting_time_payload, valid_noshow_payload
    ):
        """Unseen specialties do not crash the endpoint (OneHotEncoder ignore policy)."""
        _, headers = await create_auth_user()
        valid_waiting_time_payload["doctor_specialty"] = "Hyperbaric Space Medicine"
        valid_noshow_payload["doctor_specialty"] = "Hyperbaric Space Medicine"

        wt_resp = await client.post(
            "/api/v1/predictions/waiting-time",
            json=valid_waiting_time_payload,
            headers=headers,
        )
        assert wt_resp.status_code == 200
        assert wt_resp.json()["predicted_wait_minutes"] >= 0.0

        ns_resp = await client.post(
            "/api/v1/predictions/no-show",
            json=valid_noshow_payload,
            headers=headers,
        )
        assert ns_resp.status_code == 200
        assert 0.0 <= ns_resp.json()["no_show_probability"] <= 1.0

    async def test_prediction_service_status_endpoint(self, client: AsyncClient):
        """Authenticated GET /api/v1/predictions/status returns model status."""
        _, headers = await create_auth_user()
        response = await client.get("/api/v1/predictions/status", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "waiting_time_model" in data
        assert "noshow_model" in data
        assert data["waiting_time_model"]["is_synthetic"] is True
        assert data["noshow_model"]["is_synthetic"] is True


class TestPredictionInputValidation:
    """Verifies that invalid or out-of-range payloads return 422 Unprocessable Entity."""

    async def test_waiting_time_invalid_inputs(self, client: AsyncClient, valid_waiting_time_payload):
        """Pydantic validation catches invalid or missing fields for waiting time."""
        _, headers = await create_auth_user()

        # Missing required field
        invalid_payload = valid_waiting_time_payload.copy()
        del invalid_payload["doctor_specialty"]
        res = await client.post("/api/v1/predictions/waiting-time", json=invalid_payload, headers=headers)
        assert res.status_code == 422

        # Negative experience years
        invalid_payload = valid_waiting_time_payload.copy()
        invalid_payload["doctor_experience_years"] = -1
        res = await client.post("/api/v1/predictions/waiting-time", json=invalid_payload, headers=headers)
        assert res.status_code == 422

        # Invalid day of week (> 6)
        invalid_payload = valid_waiting_time_payload.copy()
        invalid_payload["day_of_week"] = 7
        res = await client.post("/api/v1/predictions/waiting-time", json=invalid_payload, headers=headers)
        assert res.status_code == 422

    async def test_noshow_invalid_inputs(self, client: AsyncClient, valid_noshow_payload):
        """Pydantic validation catches invalid or missing fields for no-show."""
        _, headers = await create_auth_user()

        # Negative lead time
        invalid_payload = valid_noshow_payload.copy()
        invalid_payload["lead_time_days"] = -5
        res = await client.post("/api/v1/predictions/no-show", json=invalid_payload, headers=headers)
        assert res.status_code == 422

        # Prior rate > 1.0
        invalid_payload = valid_noshow_payload.copy()
        invalid_payload["patient_prior_no_show_rate"] = 1.5
        res = await client.post("/api/v1/predictions/no-show", json=invalid_payload, headers=headers)
        assert res.status_code == 422


class TestPredictionErrorSanitization:
    """Verifies that missing artifacts or inference crashes return sanitized status codes without leaks."""

    async def test_missing_waiting_time_artifact_returns_503(
        self, client: AsyncClient, valid_waiting_time_payload, monkeypatch
    ):
        """Missing waiting-time model artifact returns 503 without leaking host paths."""
        _, headers = await create_auth_user()

        def mock_predict(*args, **kwargs):
            raise ModelArtifactNotFoundError("Internal artifact C:\\secrets\\model.joblib missing")

        monkeypatch.setattr(ml_prediction_service, "predict_waiting_time", mock_predict)

        res = await client.post("/api/v1/predictions/waiting-time", json=valid_waiting_time_payload, headers=headers)
        assert res.status_code == 503
        detail = res.json()["detail"]
        assert "temporarily unavailable" in detail.lower()
        assert "secrets" not in detail
        assert "model.joblib" not in detail

    async def test_inference_crash_returns_500_sanitized(
        self, client: AsyncClient, valid_noshow_payload, monkeypatch
    ):
        """Inference failure returns sanitized 500 without leaking stack traces or paths."""
        _, headers = await create_auth_user()

        def mock_predict(*args, **kwargs):
            raise ModelInferenceError("Numpy internal float64 segfault in /var/log/private")

        monkeypatch.setattr(ml_prediction_service, "predict_no_show", mock_predict)

        res = await client.post("/api/v1/predictions/no-show", json=valid_noshow_payload, headers=headers)
        assert res.status_code == 500
        detail = res.json()["detail"]
        assert "failed" in detail.lower()
        assert "/var/log" not in detail
        assert "traceback" not in detail.lower()


class TestZeroDatabaseMutations:
    """Verifies that invoking prediction endpoints never writes to PostgreSQL tables."""

    async def test_predictions_do_not_mutate_database(
        self, client: AsyncClient, valid_waiting_time_payload, valid_noshow_payload
    ):
        """Counts of appointments and queue entries remain unchanged before and after inference."""
        _, headers = await create_auth_user()

        async with AsyncSessionLocal() as session:
            before_appt_count = await session.scalar(select(func.count(Appointment.id)))
            before_queue_count = await session.scalar(select(func.count(QueueEntry.id)))

        # Run both predictions
        res_wt = await client.post("/api/v1/predictions/waiting-time", json=valid_waiting_time_payload, headers=headers)
        res_ns = await client.post("/api/v1/predictions/no-show", json=valid_noshow_payload, headers=headers)

        assert res_wt.status_code == 200
        assert res_ns.status_code == 200

        async with AsyncSessionLocal() as session:
            after_appt_count = await session.scalar(select(func.count(Appointment.id)))
            after_queue_count = await session.scalar(select(func.count(QueueEntry.id)))

        assert before_appt_count == after_appt_count == 0
        assert before_queue_count == after_queue_count == 0
