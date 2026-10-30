import uuid
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token
from app.models.doctor import Doctor
from tests.test_appointments import create_test_doctor_fixture, create_test_user

CLINIC_TZ = ZoneInfo("Asia/Kolkata")


def clinic_today_date():
    return datetime.now(CLINIC_TZ).date()


@pytest.mark.asyncio
async def test_complete_patient_to_doctor_workflow(client: AsyncClient):
    """
    Empirical End-to-End Test for the Complete Patient-to-Doctor Workflow:
    1. Patient Booking:
       - Patient login
       - Search and select doctor
       - Check consultation slots availability (Verify NO HTTP 500 error!)
       - Book consultation
       - Verify confirmation and booking reference
    2. Doctor Dashboard:
       - Doctor login
       - Verify dashboard statistics
       - Verify newly booked appointment appears in doctor's roster
       - View appointment details
    3. Real-Time Queue:
       - Check in patient
       - Doctor calls patient from dashboard/queue
       - Verify patient queue tracker updates to in_consultation
       - Doctor completes consultation
       - Verify final queue status updates to completed
    """
    # -------------------------------------------------------------------------
    # Setup: Isolated Doctor & Patient in Test Database
    # -------------------------------------------------------------------------
    doc_id, hosp_id = await create_test_doctor_fixture()

    async with AsyncSessionLocal() as session:
        doc_record = (await session.execute(select(Doctor).where(Doctor.id == doc_id))).scalar_one()
        doc_user_id = doc_record.user_id

    doc_token = create_access_token(user_id=doc_user_id, role="doctor")
    doc_headers = {"Authorization": f"Bearer {doc_token}"}

    patient_id, pat_headers = await create_test_user("patient")

    # -------------------------------------------------------------------------
    # 1. Patient Booking Workflow
    # -------------------------------------------------------------------------
    # A. Search for doctor in directory
    search_res = await client.get("/api/v1/doctors?specialty=Cardiology")
    assert search_res.status_code == 200, f"Doctor search failed: {search_res.text}"
    doctors = search_res.json()["items"]
    selected_doc = next((d for d in doctors if d["id"] == str(doc_id)), None)
    assert selected_doc is not None, "Created doctor must appear in search results"

    # B. Select doctor and open consultation slots availability
    target_date = (clinic_today_date() + timedelta(days=2)).isoformat()
    slots_res = await client.get(f"/api/v1/doctors/{doc_id}/slots?date={target_date}")
    # CRITICAL VERIFICATION: Confirm NO HTTP 500 error!
    assert slots_res.status_code == 200, f"Consultation slots failed with HTTP {slots_res.status_code}: {slots_res.text}"
    slots_data = slots_res.json()
    assert slots_data["is_working_day"] is True
    available_slots = [s for s in slots_data["slots"] if s["is_available"]]
    assert len(available_slots) > 0, "Expected at least one available consultation slot"
    chosen_slot_time = available_slots[0]["time"]

    # C. Book doctor consultation
    booking_payload = {
        "doctor_id": str(doc_id),
        "appointment_date": target_date,
        "appointment_time": chosen_slot_time,
        "notes": "Follow-up cardiovascular check and blood pressure review",
    }
    book_res = await client.post("/api/v1/appointments", json=booking_payload, headers=pat_headers)
    assert book_res.status_code == 201, f"Booking request failed with status {book_res.status_code}: {book_res.text}"
    booking_data = book_res.json()
    appt_id = booking_data["id"]
    appt_token = booking_data["appointment_token"]

    # D. Verify confirmation and reference token
    assert appt_token.startswith("MS-"), f"Expected token to start with 'MS-', got: {appt_token}"
    assert booking_data["status"] == "scheduled"
    assert booking_data["appointment_date"] == target_date
    assert booking_data["appointment_time"].startswith(chosen_slot_time)

    # E. Verify booking appears in patient's personal appointment list
    pat_appts_res = await client.get("/api/v1/appointments", headers=pat_headers)
    assert pat_appts_res.status_code == 200
    my_appts = pat_appts_res.json()["items"]
    assert any(a["id"] == appt_id for a in my_appts), "Booking must appear in patient's appointments"

    # -------------------------------------------------------------------------
    # 2. Doctor Dashboard Workflow
    # -------------------------------------------------------------------------
    # A. Doctor opens dashboard /me
    me_res = await client.get("/api/v1/doctors/me", headers=doc_headers)
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["id"] == str(doc_id)
    assert me_data["specialty"] == "Cardiology"

    # B. Doctor verifies dashboard statistics
    stats_res = await client.get("/api/v1/doctors/me/stats", headers=doc_headers)
    assert stats_res.status_code == 200
    stats_data = stats_res.json()
    assert "today_appointments" in stats_data
    assert "waiting_patients" in stats_data
    assert "completed_consultations" in stats_data
    assert stats_data["doctor_id"] == str(doc_id)

    # C. Doctor views assigned appointments for the booked date
    doc_appts_res = await client.get(f"/api/v1/appointments?date={target_date}", headers=doc_headers)
    assert doc_appts_res.status_code == 200
    doc_appts = doc_appts_res.json()["items"]
    matching_appt = next((a for a in doc_appts if a["id"] == appt_id), None)
    assert matching_appt is not None, f"Appointment {appt_id} must appear in doctor's roster for {target_date}"
    assert matching_appt["appointment_token"] == appt_token
    assert matching_appt["patient"]["id"] == str(patient_id)

    # D. Open single appointment details modal
    detail_res = await client.get(f"/api/v1/appointments/{appt_id}", headers=doc_headers)
    assert detail_res.status_code == 200
    detail_data = detail_res.json()
    assert detail_data["id"] == appt_id
    assert detail_data["notes"] == "Follow-up cardiovascular check and blood pressure review"

    # -------------------------------------------------------------------------
    # 3. Real-Time Queue & Consultation Lifecycle
    # -------------------------------------------------------------------------
    # Book a consultation for today so queue lifecycle can run
    today_iso = clinic_today_date().isoformat()
    today_appt_res = await client.post(
        "/api/v1/appointments",
        json={
            "doctor_id": str(doc_id),
            "appointment_date": today_iso,
            "appointment_time": "14:30",
            "problem_description": "Same-day consultation queue check-in",
        },
        headers=pat_headers,
    )
    assert today_appt_res.status_code == 201
    today_appt_id = today_appt_res.json()["id"]

    # A. Patient checks in to active daily queue
    checkin_res = await client.post(
        "/api/v1/queue/check-in",
        json={"appointment_id": today_appt_id},
        headers=pat_headers,
    )
    assert checkin_res.status_code == 201
    q_entry = checkin_res.json()
    entry_id = q_entry["id"]
    token_display = q_entry["token_display"]
    assert q_entry["status"] == "waiting"

    # B. Patient tracks personal queue status
    my_q_res = await client.get("/api/v1/queue/my", headers=pat_headers)
    assert my_q_res.status_code == 200
    my_q_data = my_q_res.json()
    assert my_q_data["status"] == "waiting"
    assert my_q_data["token_display"] == token_display

    # C. Doctor checks queue from dashboard/console
    doc_q_res = await client.get(f"/api/v1/queue/doctor/{doc_id}", headers=doc_headers)
    assert doc_q_res.status_code == 200
    doc_q_data = doc_q_res.json()
    assert any(item["id"] == entry_id for item in doc_q_data["waiting_list"])

    # D. Doctor calls patient into consultation
    call_res = await client.post(
        f"/api/v1/queue/{entry_id}/call",
        json={"notes": "Doctor called patient into consultation room"},
        headers=doc_headers,
    )
    assert call_res.status_code == 200
    called_data = call_res.json()
    assert called_data["status"] == "in_consultation"
    assert called_data["called_at"] is not None

    # Verify patient tracker updates to in_consultation
    pat_tracker_called = await client.get("/api/v1/queue/my", headers=pat_headers)
    assert pat_tracker_called.status_code == 200
    assert pat_tracker_called.json()["status"] == "in_consultation"

    # E. Doctor completes consultation
    complete_res = await client.post(
        f"/api/v1/queue/{entry_id}/complete",
        json={"notes": "Consultation concluded. Prescriptions issued."},
        headers=doc_headers,
    )
    assert complete_res.status_code == 200
    completed_data = complete_res.json()
    assert completed_data["status"] == "completed"
    assert completed_data["completed_at"] is not None

    # F. Verify final queue status
    doc_q_final = await client.get(f"/api/v1/queue/doctor/{doc_id}", headers=doc_headers)
    assert doc_q_final.status_code == 200
    assert doc_q_final.json()["current_consultation"] is None
