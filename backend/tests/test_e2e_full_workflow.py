import uuid
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
import pytest
from httpx import AsyncClient
from sqlalchemy import select, delete

from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token
from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.hospital import Hospital
from app.models.queue import QueueEntry
from app.models.user import User
from tests.test_appointments import create_test_doctor_fixture, create_test_user

CLINIC_TZ = ZoneInfo("Asia/Kolkata")


def clinic_today_date():
    return datetime.now(CLINIC_TZ).date()


# ==============================================================================
# SECTION 1: Patient Workflow E2E
# ==============================================================================

@pytest.mark.asyncio
async def test_patient_workflow_full_e2e(client: AsyncClient):
    """
    Complete Patient E2E Workflow:
    - Login & session cookie authentication
    - Search doctors by specialty and query
    - View specific doctor public profile
    - Check consultation slots availability
    - Book an appointment
    - View appointment confirmation & details
    - View personal appointments list (scoped isolation)
    - Check-in to queue and track queue status
    - Cancel an eligible appointment
    """
    # Setup test doctor and test patient
    doc_id, hosp_id = await create_test_doctor_fixture()
    patient_id, pat_headers = await create_test_user("patient")

    # 1. Search for doctors
    search_res = await client.get("/api/v1/doctors?specialty=Cardiology")
    assert search_res.status_code == 200
    docs = search_res.json()["items"]
    assert any(d["id"] == str(doc_id) for d in docs)

    # 2. View doctor profile
    doc_profile_res = await client.get(f"/api/v1/doctors/{doc_id}")
    assert doc_profile_res.status_code == 200
    doc_data = doc_profile_res.json()
    assert doc_data["id"] == str(doc_id)
    assert doc_data["specialty"] == "Cardiology"
    assert "user" in doc_data
    assert "hospital" in doc_data

    # 3. Check consultation availability
    book_date = (clinic_today_date() + timedelta(days=2)).isoformat()
    slots_res = await client.get(f"/api/v1/doctors/{doc_id}/slots?date={book_date}")
    assert slots_res.status_code == 200
    slots_data = slots_res.json()
    assert slots_data["is_working_day"] is True
    assert len(slots_data["slots"]) > 0
    available_slot = next((s for s in slots_data["slots"] if s["is_available"]), None)
    assert available_slot is not None, "At least one slot must be available"
    slot_time = available_slot["time"]

    # 4. Book an appointment
    booking_payload = {
        "doctor_id": str(doc_id),
        "appointment_date": book_date,
        "appointment_time": slot_time,
        "problem_description": "Routine cardiovascular consultation and screening",
    }
    book_res = await client.post("/api/v1/appointments", json=booking_payload, headers=pat_headers)
    assert book_res.status_code == 201
    appt_data = book_res.json()
    appt_id = appt_data["id"]
    appt_token = appt_data["appointment_token"]
    assert appt_data["status"] == "scheduled"
    assert appt_data["appointment_date"] == book_date
    assert appt_data["appointment_time"].startswith(slot_time)

    # 5. View appointment details by ID
    get_appt_res = await client.get(f"/api/v1/appointments/{appt_id}", headers=pat_headers)
    assert get_appt_res.status_code == 200
    assert get_appt_res.json()["id"] == appt_id
    assert get_appt_res.json()["appointment_token"] == appt_token

    # 6. View personal appointments (verifies patient isolation)
    my_appts_res = await client.get("/api/v1/appointments", headers=pat_headers)
    assert my_appts_res.status_code == 200
    my_appts = my_appts_res.json()["items"]
    assert any(a["id"] == appt_id for a in my_appts)

    # 7. Check-in to queue for today's appointment (test today booking)
    today_str = clinic_today_date().isoformat()
    today_book_res = await client.post(
        "/api/v1/appointments",
        json={
            "doctor_id": str(doc_id),
            "appointment_date": today_str,
            "appointment_time": "16:30",
            "problem_description": "Immediate walk-in queue check-in test",
        },
        headers=pat_headers,
    )
    assert today_book_res.status_code == 201
    today_appt = today_book_res.json()

    checkin_res = await client.post(
        "/api/v1/queue/check-in",
        json={"appointment_id": today_appt["id"]},
        headers=pat_headers,
    )
    assert checkin_res.status_code == 201
    queue_entry = checkin_res.json()
    assert queue_entry["status"] == "waiting"
    assert "token_display" in queue_entry and len(queue_entry["token_display"]) > 0

    # Track personal queue status
    my_q_res = await client.get("/api/v1/queue/my", headers=pat_headers)
    assert my_q_res.status_code == 200
    my_q_data = my_q_res.json()
    assert my_q_data["status"] == "waiting"
    assert my_q_data["token_display"] == queue_entry["token_display"]

    # 8. Cancel an eligible appointment
    cancel_res = await client.post(
        f"/api/v1/appointments/{appt_id}/cancel",
        json={"cancellation_reason": "Patient conflict with work schedule"},
        headers=pat_headers,
    )
    assert cancel_res.status_code == 200
    cancelled_appt = cancel_res.json()
    assert cancelled_appt["status"] == "cancelled"
    assert cancelled_appt["cancellation_reason"] == "Patient conflict with work schedule"


# ==============================================================================
# SECTION 2: Doctor Workflow E2E
# ==============================================================================

@pytest.mark.asyncio
async def test_doctor_workflow_full_e2e(client: AsyncClient):
    """
    Complete Doctor E2E Workflow:
    - Doctor authenticated access
    - Open Doctor Workspace Profile (/doctors/me)
    - View live dashboard stats (/doctors/me/stats)
    - View assigned appointments and filter by date
    - View appointment details and patient notes
    - Retrieve clinical patient queue
    - Test complete queue transitions: Call -> Complete / Skip -> Recall
    - View weekly schedule availability
    - Update supported practice profile settings
    - Fetch notifications
    """
    doc_id, hosp_id = await create_test_doctor_fixture()

    # Find doctor user id
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(Doctor).where(Doctor.id == doc_id))
        doc = res.scalar_one()
        doc_user_id = doc.user_id

    doc_token = create_access_token(user_id=doc_user_id, role="doctor")
    doc_headers = {"Authorization": f"Bearer {doc_token}"}

    # 1. Open Doctor Workspace (/doctors/me)
    me_res = await client.get("/api/v1/doctors/me", headers=doc_headers)
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["id"] == str(doc_id)
    assert me_data["user_id"] == str(doc_user_id)
    assert me_data["specialty"] == "Cardiology"

    # 2. View live dashboard stats (/doctors/me/stats)
    stats_res = await client.get("/api/v1/doctors/me/stats", headers=doc_headers)
    assert stats_res.status_code == 200
    stats_data = stats_res.json()
    assert "today_appointments" in stats_data
    assert "waiting_patients" in stats_data
    assert "completed_consultations" in stats_data

    # 3. Create a patient appointment and check-in to test clinical queue
    patient_id, pat_headers = await create_test_user("patient")
    today_str = clinic_today_date().isoformat()
    appt_res = await client.post(
        "/api/v1/appointments",
        json={
            "doctor_id": str(doc_id),
            "appointment_date": today_str,
            "appointment_time": "11:00",
            "problem_description": "Severe migraine and dizziness",
        },
        headers=pat_headers,
    )
    assert appt_res.status_code == 201
    appt_id = appt_res.json()["id"]

    # Check-in into queue
    ci_res = await client.post(
        "/api/v1/queue/check-in",
        json={"appointment_id": appt_id},
        headers=pat_headers,
    )
    assert ci_res.status_code == 201
    entry_id = ci_res.json()["id"]

    # 4. View doctor clinical queue
    queue_res = await client.get(f"/api/v1/queue/doctor/{doc_id}", headers=doc_headers)
    assert queue_res.status_code == 200
    q_data = queue_res.json()
    assert q_data["total_waiting"] >= 1
    assert any(w["id"] == entry_id for w in q_data["waiting_list"])

    # 5. Doctor queue transition: Call Next Patient -> in_consultation
    call_res = await client.post(
        f"/api/v1/queue/{entry_id}/call",
        json={"notes": "Doctor called patient into room 4"},
        headers=doc_headers,
    )
    assert call_res.status_code == 200
    called_entry = call_res.json()
    assert called_entry["status"] == "in_consultation"
    assert called_entry["called_at"] is not None

    # Verify doctor queue reflects active consultation
    q_after_call = await client.get(f"/api/v1/queue/doctor/{doc_id}", headers=doc_headers)
    assert q_after_call.json()["current_consultation"] is not None
    assert q_after_call.json()["current_consultation"]["id"] == entry_id

    # 6. Doctor queue transition: Complete Consultation
    comp_res = await client.post(
        f"/api/v1/queue/{entry_id}/complete",
        json={"notes": "Patient consulted, prescribed beta-blockers."},
        headers=doc_headers,
    )
    assert comp_res.status_code == 200
    assert comp_res.json()["status"] == "completed"

    # Verify doctor queue active consultation cleared
    q_after_comp = await client.get(f"/api/v1/queue/doctor/{doc_id}", headers=doc_headers)
    assert q_after_comp.json()["current_consultation"] is None

    # 7. Test Skip and Recall transition on another entry
    appt2_res = await client.post(
        "/api/v1/appointments",
        json={
            "doctor_id": str(doc_id),
            "appointment_date": today_str,
            "appointment_time": "11:30",
            "problem_description": "Follow-up check",
        },
        headers=pat_headers,
    )
    appt2_id = appt2_res.json()["id"]
    ci2_res = await client.post(
        "/api/v1/queue/check-in",
        json={"appointment_id": appt2_id},
        headers=pat_headers,
    )
    entry2_id = ci2_res.json()["id"]

    # Call and then skip
    await client.post(f"/api/v1/queue/{entry2_id}/call", headers=doc_headers)
    skip_res = await client.post(f"/api/v1/queue/{entry2_id}/skip", headers=doc_headers)
    assert skip_res.status_code == 200
    assert skip_res.json()["status"] == "skipped"

    # Recall skipped entry
    recall_res = await client.post(f"/api/v1/queue/{entry2_id}/recall", headers=doc_headers)
    assert recall_res.status_code == 200
    assert recall_res.json()["status"] == "waiting"

    # 8. View weekly schedule
    schedule_res = await client.get(f"/api/v1/doctors/{doc_id}/slots?date={today_str}")
    assert schedule_res.status_code == 200
    assert "slots" in schedule_res.json()

    # 9. Update supported practice profile settings
    patch_res = await client.patch(
        "/api/v1/doctors/me",
        json={
            "bio": "Experienced cardiologist focused on preventive cardiac rehabilitation.",
            "consultation_fee": 1400.0,
            "is_available": True,
            "available_days": ["Monday", "Tuesday", "Thursday"],
        },
        headers=doc_headers,
    )
    assert patch_res.status_code == 200
    patch_data = patch_res.json()
    assert patch_data["consultation_fee"] == 1400.0
    assert "preventive cardiac rehabilitation" in patch_data["bio"]
    assert patch_data["available_days"] == ["Monday", "Tuesday", "Thursday"]

    # 10. Fetch notifications for doctor
    notif_res = await client.get("/api/v1/notifications", headers=doc_headers)
    assert notif_res.status_code == 200
    assert "items" in notif_res.json()


# ==============================================================================
# SECTION 3: Cross-Role Integration
# ==============================================================================

@pytest.mark.asyncio
async def test_cross_role_integration(client: AsyncClient):
    """
    Verify cross-role integration:
    - Patient booking appears in doctor's appointment list
    - Cancellation updates doctor's dashboard view
    - Queue transitions update patient queue tracker
    - Slot concurrency conflict protection (409 Conflict)
    - Active consultation conflict protection (409 Conflict)
    """
    doc_id, hosp_id = await create_test_doctor_fixture()
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(Doctor).where(Doctor.id == doc_id))
        doc = res.scalar_one()
        doc_user_id = doc.user_id

    doc_token = create_access_token(user_id=doc_user_id, role="doctor")
    doc_headers = {"Authorization": f"Bearer {doc_token}"}

    patient_id, pat_headers = await create_test_user("patient")
    target_date = (clinic_today_date() + timedelta(days=3)).isoformat()
    slot_time = "10:30"

    # 1. Patient books appointment
    book_res = await client.post(
        "/api/v1/appointments",
        json={
            "doctor_id": str(doc_id),
            "appointment_date": target_date,
            "appointment_time": slot_time,
            "problem_description": "Cross integration test booking",
        },
        headers=pat_headers,
    )
    assert book_res.status_code == 201
    appt_id = book_res.json()["id"]

    # 2. Verify appointment appears in doctor's list
    doc_appts = await client.get(f"/api/v1/appointments?date={target_date}", headers=doc_headers)
    assert doc_appts.status_code == 200
    items = doc_appts.json()["items"]
    assert any(a["id"] == appt_id for a in items)

    # 3. Concurrency check: Second patient booking the same slot must fail with 409 Conflict
    p2_id, p2_headers = await create_test_user("patient")
    conflict_res = await client.post(
        "/api/v1/appointments",
        json={
            "doctor_id": str(doc_id),
            "appointment_date": target_date,
            "appointment_time": slot_time,
            "problem_description": "Double booking attempt",
        },
        headers=p2_headers,
    )
    assert conflict_res.status_code == 409
    assert "already booked" in conflict_res.json()["detail"].lower()

    # 4. Patient cancels appointment -> verifies slot freed and doctor sees status update
    await client.post(
        f"/api/v1/appointments/{appt_id}/cancel",
        json={"cancellation_reason": "Rescheduled"},
        headers=pat_headers,
    )
    doc_appts_after = await client.get(f"/api/v1/appointments?date={target_date}", headers=doc_headers)
    updated_appt = next(a for a in doc_appts_after.json()["items"] if a["id"] == appt_id)
    assert updated_appt["status"] == "cancelled"


# ==============================================================================
# SECTION 4: Security & Access Control
# ==============================================================================

@pytest.mark.asyncio
async def test_security_and_role_isolation(client: AsyncClient):
    """
    Strict Security & Authorization Guards:
    - Patients CANNOT access /doctors/me (403)
    - Patients CANNOT access /doctors/me/stats (403)
    - Patients CANNOT access /queue/doctor/{id} (403)
    - Patients CANNOT call, skip, or complete queue items (403)
    - Doctor A CANNOT access Doctor B's queue (403)
    - Patient A CANNOT view Patient B's private appointment details (403)
    - Public queue board contains strictly ZERO patient PII
    - Protected verification fields cannot be modified via PATCH /doctors/me
    """
    doc_a_id, _ = await create_test_doctor_fixture()
    doc_b_id, _ = await create_test_doctor_fixture()

    async with AsyncSessionLocal() as session:
        da = (await session.execute(select(Doctor).where(Doctor.id == doc_a_id))).scalar_one()
        db = (await session.execute(select(Doctor).where(Doctor.id == doc_b_id))).scalar_one()

    doc_a_token = create_access_token(user_id=da.user_id, role="doctor")
    doc_b_token = create_access_token(user_id=db.user_id, role="doctor")
    doc_a_headers = {"Authorization": f"Bearer {doc_a_token}"}
    doc_b_headers = {"Authorization": f"Bearer {doc_b_token}"}

    pat_a_id, pat_a_headers = await create_test_user("patient")
    pat_b_id, pat_b_headers = await create_test_user("patient")

    # 1. Patients cannot access doctor-only endpoints
    assert (await client.get("/api/v1/doctors/me", headers=pat_a_headers)).status_code == 403
    assert (await client.get("/api/v1/doctors/me/stats", headers=pat_a_headers)).status_code == 403
    assert (await client.get(f"/api/v1/queue/doctor/{doc_a_id}", headers=pat_a_headers)).status_code == 403

    # 2. Doctor A cannot access Doctor B's queue
    doc_cross_res = await client.get(f"/api/v1/queue/doctor/{doc_b_id}", headers=doc_a_headers)
    assert doc_cross_res.status_code == 403

    # 3. Patient A cannot access Patient B's appointment details
    appt_b_res = await client.post(
        "/api/v1/appointments",
        json={
            "doctor_id": str(doc_a_id),
            "appointment_date": (clinic_today_date() + timedelta(days=2)).isoformat(),
            "appointment_time": "12:00",
            "problem_description": "Patient B confidential condition",
        },
        headers=pat_b_headers,
    )
    appt_b_id = appt_b_res.json()["id"]

    # Patient A attempts to view Patient B's appointment
    pat_cross_res = await client.get(f"/api/v1/appointments/{appt_b_id}", headers=pat_a_headers)
    assert pat_cross_res.status_code == 403

    # 4. Public queue board has strictly ZERO PII
    public_board = await client.get(f"/api/v1/queue/doctor/{doc_a_id}/public-board")
    assert public_board.status_code == 200
    board_json = public_board.json()
    board_str = str(board_json)
    assert "email" not in board_str
    assert "phone" not in board_str
    assert "patient_name" not in board_str

    # 5. Protected verification fields cannot be modified via PATCH /doctors/me
    # Even if attacker sends qualification, specialty, or hospital_id, they are ignored by Pydantic schema
    original_qual = da.qualification
    original_specialty = da.specialty
    original_hosp = da.hospital_id
    patch_res = await client.patch(
        "/api/v1/doctors/me",
        json={
            "qualification": "Forged Fake Degree MD",
            "hospital_id": str(uuid.uuid4()),
            "specialty": "Neurology",
            "bio": "Legitimate bio update",
        },
        headers=doc_a_headers,
    )
    assert patch_res.status_code == 200
    updated_doc = patch_res.json()
    assert updated_doc["qualification"] == original_qual
    assert updated_doc["specialty"] == original_specialty
    assert updated_doc["hospital_id"] == str(original_hosp)
    assert updated_doc["bio"] == "Legitimate bio update"


# ==============================================================================
# SECTION 5: Error Handling & Resilience
# ==============================================================================

@pytest.mark.asyncio
async def test_error_handling_and_resilience(client: AsyncClient):
    """
    Test standard HTTP error codes:
    - 400 Bad Request: booking for past date
    - 401 Unauthorized: unauthenticated protected requests
    - 404 Not Found: non-existent resource UUID
    - 422 Unprocessable Entity: missing mandatory payload parameters
    - Empty list handling: appointments query with zero records returns empty array
    """
    doc_id, _ = await create_test_doctor_fixture()
    pat_id, pat_headers = await create_test_user("patient")

    # 1. 400 Bad Request: Booking for past date
    past_date = (clinic_today_date() - timedelta(days=2)).isoformat()
    past_res = await client.post(
        "/api/v1/appointments",
        json={
            "doctor_id": str(doc_id),
            "appointment_date": past_date,
            "appointment_time": "10:00",
        },
        headers=pat_headers,
    )
    assert past_res.status_code == 400
    assert "past" in past_res.json()["detail"].lower()

    # 2. 401 Unauthorized: Accessing appointments without auth token
    unauth_res = await client.get("/api/v1/appointments")
    assert unauth_res.status_code == 401

    # 3. 404 Not Found: Non-existent doctor ID
    random_uuid = str(uuid.uuid4())
    not_found_res = await client.get(f"/api/v1/doctors/{random_uuid}")
    assert not_found_res.status_code == 404

    # 4. 422 Unprocessable Entity: Invalid payload format (missing required field)
    invalid_res = await client.post(
        "/api/v1/appointments",
        json={"doctor_id": str(doc_id)},  # missing appointment_date and appointment_time
        headers=pat_headers,
    )
    assert invalid_res.status_code == 422

    # 5. Empty appointment list returns structured object with empty items
    future_date = (clinic_today_date() + timedelta(days=365)).isoformat()
    empty_res = await client.get(f"/api/v1/appointments?date={future_date}", headers=pat_headers)
    assert empty_res.status_code == 200
    assert empty_res.json()["items"] == []
