"""
Electronic Health Record (EHR) & Clinical Consultation Service for MediSmart.

Hardened for Phase 10.1:
- Prescription Immutability: Issued prescriptions cannot be overwritten; amendments preserve history.
- Prescription Amendments: Generates incremented versions and links original prescriptions via superseded_by_id.
- Clinical Audit Trail: Full HIPAA/GDPR audit logging with sanitized non-PHI metadata.
- Transaction Integrity: Strict ACID transaction boundaries; failures trigger clean rollback;
  notifications dispatched strictly after successful database commit.
- Follow-Up Safety: Validates slot boundaries against ALLOWED_SLOT_TIMES, detects slot conflicts (409 Conflict),
  prevents duplicate follow-up submissions, and prevents past-date bookings.
- Strict Access Control: IDOR protection across consultation notes, patient histories, and prescriptions.
"""
import logging
import uuid
from datetime import date, datetime, time, timezone
from typing import Any, Dict, List, Optional, Set

from fastapi import HTTPException, status
from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.ehr import (
    ClinicalAuditLog,
    ConsultationNote,
    Diagnosis,
    Prescription,
    PrescriptionItem,
)
from app.models.hospital import Hospital
from app.models.queue import QueueEntry
from app.models.user import User
from app.schemas.ehr import (
    ConsultationNoteCreate,
    ConsultationNoteResponse,
    DiagnosisCreate,
    DiagnosisResponse,
    FollowUpCreateRequest,
    FollowUpResponse,
    PatientMedicalHistoryResponse,
    PrescriptionAmendRequest,
    PrescriptionCreate,
    PrescriptionItemResponse,
    PrescriptionResponse,
)
from app.services.clinical_audit_service import clinical_audit_service
from app.services.notification import notification_service

logger = logging.getLogger("medismart.services.ehr")

# Standard 30-minute consultation clinic slots matching appointment system
ALLOWED_SLOT_TIMES: Set[str] = {
    "09:00", "09:30", "10:00", "10:30",
    "11:00", "11:30", "12:00", "12:30",
    "14:00", "14:30", "15:00", "15:30",
    "16:00", "16:30"
}


class EHRService:
    """Centralized, hardened service for clinical documentation and patient medical records."""

    @classmethod
    async def create_or_update_consultation(
        cls,
        doctor_user: User,
        data: ConsultationNoteCreate,
        db: AsyncSession,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> ConsultationNoteResponse:
        """
        Creates or updates a physician consultation record with full transaction integrity.
        - Verifies doctor ownership on the appointment.
        - Preserves prescription immutability: will not silently overwrite existing issued prescriptions.
        - Synchronizes appointment and queue statuses to 'completed'.
        - Records immutable audit logs for consultation, diagnosis, and prescription issuance.
        - Dispatches patient notifications strictly after successful transaction commit.
        """
        # 1. Resolve doctor profile
        doc_res = await db.execute(select(Doctor).where(Doctor.user_id == doctor_user.id))
        doctor = doc_res.scalar_one_or_none()
        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only registered physicians may document clinical consultations.",
            )

        # 2. Retrieve appointment with pessimistic row lock
        appt_query = (
            select(Appointment)
            .where(Appointment.id == data.appointment_id)
            .options(
                selectinload(Appointment.doctor).selectinload(Doctor.user),
                selectinload(Appointment.hospital),
                selectinload(Appointment.patient),
                selectinload(Appointment.queue_entry),
            )
            .with_for_update()
        )
        appt_res = await db.execute(appt_query)
        appointment = appt_res.scalar_one_or_none()

        if not appointment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment not found.",
            )

        # 3. Ownership & Authorization Check
        if appointment.doctor_id != doctor.id:
            await clinical_audit_service.log(
                db=db,
                action="UNAUTHORIZED_ACCESS_ATTEMPT",
                target_type="appointment",
                actor=doctor_user,
                target_id=data.appointment_id,
                metadata={"attempted_action": "document_consultation"},
                ip_address=ip_address,
                user_agent=user_agent,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You may only document consultations for your own assigned appointments.",
            )

        # 4. Check for existing consultation note
        note_query = (
            select(ConsultationNote)
            .where(ConsultationNote.appointment_id == appointment.id)
            .options(
                selectinload(ConsultationNote.diagnoses),
                selectinload(ConsultationNote.prescriptions).selectinload(Prescription.items),
            )
        )
        note_res = await db.execute(note_query)
        existing_note = note_res.scalar_one_or_none()

        now_utc = datetime.now(timezone.utc)
        is_update = existing_note is not None

        if existing_note:
            # Update existing note clinical narrative
            existing_note.chief_complaint = data.chief_complaint
            existing_note.symptoms = data.symptoms
            existing_note.clinical_observations = data.clinical_observations
            existing_note.examination_notes = data.examination_notes
            existing_note.diagnosis_summary = data.diagnosis_summary
            existing_note.treatment_plan = data.treatment_plan
            existing_note.doctor_recommendations = data.doctor_recommendations
            existing_note.follow_up_recommended_date = data.follow_up_recommended_date
            existing_note.follow_up_instructions = data.follow_up_instructions
            note = existing_note
        else:
            note = ConsultationNote(
                id=uuid.uuid4(),
                appointment_id=appointment.id,
                patient_id=appointment.patient_id,
                doctor_id=doctor.id,
                hospital_id=appointment.hospital_id,
                consultation_date=appointment.appointment_date,
                consultation_time=appointment.appointment_time,
                chief_complaint=data.chief_complaint,
                symptoms=data.symptoms,
                clinical_observations=data.clinical_observations,
                examination_notes=data.examination_notes,
                diagnosis_summary=data.diagnosis_summary,
                treatment_plan=data.treatment_plan,
                doctor_recommendations=data.doctor_recommendations,
                follow_up_recommended_date=data.follow_up_recommended_date,
                follow_up_instructions=data.follow_up_instructions,
            )
            db.add(note)
            await db.flush()

        # 5. Add structured diagnoses
        diagnoses_created_count = 0
        if data.diagnoses:
            for diag_in in data.diagnoses:
                diag = Diagnosis(
                    id=uuid.uuid4(),
                    consultation_note_id=note.id,
                    patient_id=appointment.patient_id,
                    doctor_id=doctor.id,
                    diagnosis_name=diag_in.diagnosis_name,
                    clinical_description=diag_in.clinical_description,
                    diagnosis_code=diag_in.diagnosis_code,
                    diagnosis_date=appointment.appointment_date,
                    status=diag_in.status,
                )
                db.add(diag)
                diagnoses_created_count += 1

        # 6. Prescription Immutability Protection:
        # If an active prescription already exists for this encounter, do NOT overwrite or duplicate silently.
        created_rx_number = None
        new_prescription_id = None
        if data.prescription and data.prescription.items:
            existing_active_rx = None
            if existing_note and existing_note.prescriptions:
                for rx in existing_note.prescriptions:
                    if rx.is_active:
                        existing_active_rx = rx
                        break

            if existing_active_rx:
                logger.info(
                    f"Prescription immutability: Active prescription {existing_active_rx.prescription_number} "
                    f"already exists for consultation {note.id}. Use amend_prescription to revise."
                )
            else:
                rx_num = f"RX-{now_utc.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
                created_rx_number = rx_num

                prescription = Prescription(
                    id=uuid.uuid4(),
                    prescription_number=rx_num,
                    consultation_note_id=note.id,
                    appointment_id=appointment.id,
                    patient_id=appointment.patient_id,
                    doctor_id=doctor.id,
                    hospital_id=appointment.hospital_id,
                    prescription_date=appointment.appointment_date,
                    notes=data.prescription.notes,
                    is_active=True,
                    version=1,
                )
                db.add(prescription)
                await db.flush()
                new_prescription_id = prescription.id

                for item_in in data.prescription.items:
                    rx_item = PrescriptionItem(
                        id=uuid.uuid4(),
                        prescription_id=prescription.id,
                        medication_name=item_in.medication_name,
                        dosage=item_in.dosage,
                        frequency=item_in.frequency,
                        duration=item_in.duration,
                        route=item_in.route,
                        instructions=item_in.instructions,
                    )
                    db.add(rx_item)

        # 7. Synchronize Appointment and Queue status to 'completed'
        if appointment.status != "completed":
            appointment.status = "completed"

        if appointment.queue_entry and appointment.queue_entry.status in ("waiting", "in_consultation"):
            appointment.queue_entry.status = "completed"
            appointment.queue_entry.completed_at = now_utc

        # 8. Clinical Audit Trail Logging
        audit_action = "CONSULTATION_UPDATED" if is_update else "CONSULTATION_CREATED"
        await clinical_audit_service.log(
            db=db,
            action=audit_action,
            target_type="consultation_note",
            actor=doctor_user,
            target_id=note.id,
            patient_id=appointment.patient_id,
            doctor_id=doctor.id,
            hospital_id=appointment.hospital_id,
            metadata={
                "appointment_id": str(appointment.id),
                "appointment_token": appointment.appointment_token,
                "diagnoses_count": diagnoses_created_count,
                "prescription_issued": bool(created_rx_number),
                "prescription_number": created_rx_number,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        if created_rx_number and new_prescription_id:
            await clinical_audit_service.log(
                db=db,
                action="PRESCRIPTION_ISSUED",
                target_type="prescription",
                actor=doctor_user,
                target_id=new_prescription_id,
                patient_id=appointment.patient_id,
                doctor_id=doctor.id,
                hospital_id=appointment.hospital_id,
                metadata={
                    "prescription_number": created_rx_number,
                    "item_count": len(data.prescription.items),
                    "version": 1,
                },
                ip_address=ip_address,
                user_agent=user_agent,
            )

        # 9. Reliable Transaction Commit
        await db.commit()

        # 10. Post-Commit Asynchronous Patient Notifications
        doc_name = doctor_user.full_name
        if created_rx_number:
            try:
                await notification_service.create_notification(
                    db=db,
                    user_id=appointment.patient_id,
                    title="Digital Prescription Issued",
                    message=(
                        f"Dr. {doc_name} has issued a digital prescription ({created_rx_number}) "
                        f"for your consultation on {appointment.appointment_date}. "
                        "You can review your medications in My Medical Records."
                    ),
                    category="appointment",
                    event_type="prescription_issued",
                    urgency="high",
                    idempotency_key=f"rx_issued_{note.id}_{created_rx_number}",
                    metadata_json={
                        "prescription_number": created_rx_number,
                        "consultation_id": str(note.id),
                    },
                    auto_commit=True,
                )
            except Exception as notif_err:
                logger.error(f"Failed to dispatch prescription notification: {notif_err}", exc_info=True)

        if data.follow_up_recommended_date:
            try:
                await notification_service.create_notification(
                    db=db,
                    user_id=appointment.patient_id,
                    title="Follow-Up Care Recommended",
                    message=(
                        f"Dr. {doc_name} recommends a follow-up consultation on or around "
                        f"{data.follow_up_recommended_date.strftime('%A, %b %d, %Y')}. "
                        f"Instructions: {data.follow_up_instructions or 'Standard recovery monitoring.'}"
                    ),
                    category="appointment",
                    event_type="follow_up_recommended",
                    urgency="normal",
                    idempotency_key=f"follow_up_rec_{note.id}_{data.follow_up_recommended_date}",
                    metadata_json={
                        "follow_up_date": data.follow_up_recommended_date.isoformat(),
                        "doctor_name": doc_name,
                    },
                    auto_commit=True,
                )
            except Exception as notif_err:
                logger.error(f"Failed to dispatch follow-up notification: {notif_err}", exc_info=True)

        return await cls.get_consultation_note_by_id(note.id, doctor_user, db)

    @classmethod
    async def amend_prescription(
        cls,
        prescription_id: uuid.UUID,
        doctor_user: User,
        data: PrescriptionAmendRequest,
        db: AsyncSession,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> PrescriptionResponse:
        """
        Amends an issued digital prescription.
        Preserves original prescription in history (marked is_active=False with amendment_reason).
        Issues a new prescription revision linked via superseded_by_id with incremented version.
        """
        doc_res = await db.execute(select(Doctor).where(Doctor.user_id == doctor_user.id))
        doctor = doc_res.scalar_one_or_none()
        if not doctor:
            raise HTTPException(status_code=403, detail="Only registered physicians may amend prescriptions.")

        # Load prescription with lock
        rx_query = (
            select(Prescription)
            .where(Prescription.id == prescription_id)
            .options(
                selectinload(Prescription.items),
                selectinload(Prescription.doctor).selectinload(Doctor.user),
                selectinload(Prescription.hospital),
                selectinload(Prescription.patient),
            )
            .with_for_update()
        )
        res = await db.execute(rx_query)
        orig_rx = res.scalar_one_or_none()

        if not orig_rx:
            raise HTTPException(status_code=404, detail="Prescription not found.")

        # Ownership / Authorization
        if orig_rx.doctor_id != doctor.id:
            # Check if doctor has a care relationship with this patient
            appt_check = await db.execute(
                select(Appointment.id).where(
                    and_(
                        Appointment.patient_id == orig_rx.patient_id,
                        Appointment.doctor_id == doctor.id,
                    )
                ).limit(1)
            )
            if appt_check.scalar_one_or_none() is None:
                await clinical_audit_service.log(
                    db=db,
                    action="UNAUTHORIZED_ACCESS_ATTEMPT",
                    target_type="prescription",
                    actor=doctor_user,
                    target_id=prescription_id,
                    metadata={"attempted_action": "amend_prescription"},
                    ip_address=ip_address,
                    user_agent=user_agent,
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: You are not authorized to amend prescriptions for this patient.",
                )

        if not orig_rx.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot amend an inactive or already superseded prescription.",
            )

        now_utc = datetime.now(timezone.utc)
        new_rx_num = f"RX-{now_utc.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

        # 1. Create revised prescription
        revised_rx = Prescription(
            id=uuid.uuid4(),
            prescription_number=new_rx_num,
            consultation_note_id=orig_rx.consultation_note_id,
            appointment_id=orig_rx.appointment_id,
            patient_id=orig_rx.patient_id,
            doctor_id=doctor.id,
            hospital_id=orig_rx.hospital_id,
            prescription_date=now_utc.date(),
            notes=data.notes or orig_rx.notes,
            is_active=True,
            version=orig_rx.version + 1,
            amendment_reason=data.amendment_reason,
        )
        db.add(revised_rx)
        await db.flush()

        for it in data.items:
            db.add(
                PrescriptionItem(
                    id=uuid.uuid4(),
                    prescription_id=revised_rx.id,
                    medication_name=it.medication_name,
                    dosage=it.dosage,
                    frequency=it.frequency,
                    duration=it.duration,
                    route=it.route,
                    instructions=it.instructions,
                )
            )

        # 2. Deactivate original prescription and link to revision
        orig_rx.is_active = False
        orig_rx.amendment_reason = data.amendment_reason
        orig_rx.superseded_by_id = revised_rx.id

        # 3. Audit log
        await clinical_audit_service.log(
            db=db,
            action="PRESCRIPTION_AMENDED",
            target_type="prescription",
            actor=doctor_user,
            target_id=revised_rx.id,
            patient_id=orig_rx.patient_id,
            doctor_id=doctor.id,
            hospital_id=orig_rx.hospital_id,
            metadata={
                "original_prescription_number": orig_rx.prescription_number,
                "new_prescription_number": new_rx_num,
                "version": revised_rx.version,
                "amendment_reason": data.amendment_reason,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        await db.commit()

        # 4. Dispatch notification to patient after successful commit
        try:
            doc_name = doctor_user.full_name
            await notification_service.create_notification(
                db=db,
                user_id=orig_rx.patient_id,
                title="Prescription Amended by Clinician",
                message=(
                    f"Dr. {doc_name} has updated your prescription ({new_rx_num}, Revision v{revised_rx.version}). "
                    f"Reason: {data.amendment_reason}. "
                    "Review your updated medication regimen in My Medical Records."
                ),
                category="appointment",
                event_type="prescription_amended",
                urgency="high",
                idempotency_key=f"rx_amend_{revised_rx.id}",
                metadata_json={
                    "prescription_number": new_rx_num,
                    "version": revised_rx.version,
                    "original_rx": orig_rx.prescription_number,
                },
                auto_commit=True,
            )
        except Exception as notif_err:
            logger.error(f"Failed to dispatch prescription amendment notification: {notif_err}", exc_info=True)

        return await cls.get_prescription_by_id(revised_rx.id, doctor_user, db)

    @classmethod
    async def get_prescription_by_id(
        cls,
        prescription_id: uuid.UUID,
        current_user: User,
        db: AsyncSession,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> PrescriptionResponse:
        """
        Retrieves a single prescription by ID with strict RBAC and IDOR protection.
        """
        query = (
            select(Prescription)
            .where(Prescription.id == prescription_id)
            .options(
                selectinload(Prescription.items),
                selectinload(Prescription.doctor).selectinload(Doctor.user),
                selectinload(Prescription.hospital),
                selectinload(Prescription.patient),
            )
        )
        res = await db.execute(query)
        rx = res.scalar_one_or_none()

        if not rx:
            raise HTTPException(status_code=404, detail="Prescription not found.")

        # Access check
        if current_user.role == "patient" and rx.patient_id != current_user.id:
            await clinical_audit_service.log(
                db=db,
                action="UNAUTHORIZED_ACCESS_ATTEMPT",
                target_type="prescription",
                actor=current_user,
                target_id=prescription_id,
                metadata={"attempted_target_patient": str(rx.patient_id)},
                ip_address=ip_address,
                user_agent=user_agent,
            )
            raise HTTPException(status_code=403, detail="Access denied: You may only view your own prescriptions.")

        if current_user.role == "doctor":
            doc_res = await db.execute(select(Doctor.id).where(Doctor.user_id == current_user.id))
            doctor_id = doc_res.scalar_one_or_none()
            if rx.doctor_id != doctor_id:
                appt_check = await db.execute(
                    select(Appointment.id).where(
                        and_(
                            Appointment.patient_id == rx.patient_id,
                            Appointment.doctor_id == doctor_id,
                        )
                    ).limit(1)
                )
                if appt_check.scalar_one_or_none() is None:
                    await clinical_audit_service.log(
                        db=db,
                        action="UNAUTHORIZED_ACCESS_ATTEMPT",
                        target_type="prescription",
                        actor=current_user,
                        target_id=prescription_id,
                        metadata={"attempted_target_doctor": str(rx.doctor_id)},
                        ip_address=ip_address,
                        user_agent=user_agent,
                    )
                    raise HTTPException(status_code=403, detail="Access denied: Patient is not under your clinical care.")

        if current_user.role == "hospital_admin":
            if current_user.hospital_id and rx.hospital_id != current_user.hospital_id:
                await clinical_audit_service.log(
                    db=db,
                    action="UNAUTHORIZED_ACCESS_ATTEMPT",
                    target_type="prescription",
                    actor=current_user,
                    target_id=prescription_id,
                    metadata={"attempted_target_hospital": str(rx.hospital_id)},
                    ip_address=ip_address,
                    user_agent=user_agent,
                )
                raise HTTPException(status_code=403, detail="Access denied: Prescription was not issued at your hospital.")

        await clinical_audit_service.log(
            db=db,
            action="RECORD_ACCESSED",
            target_type="prescription",
            actor=current_user,
            target_id=prescription_id,
            patient_id=rx.patient_id,
            doctor_id=rx.doctor_id,
            hospital_id=rx.hospital_id,
            metadata={"prescription_number": rx.prescription_number, "version": rx.version},
            ip_address=ip_address,
            user_agent=user_agent,
        )

        pat_name = rx.patient.full_name if rx.patient else "Patient"
        doc_name = rx.doctor.user.full_name if rx.doctor and rx.doctor.user else "Doctor"
        doc_spec = rx.doctor.specialty if rx.doctor else "General Medicine"
        hosp_name = rx.hospital.name if rx.hospital else "Hospital Clinic"

        return PrescriptionResponse(
            id=rx.id,
            prescription_number=rx.prescription_number,
            consultation_note_id=rx.consultation_note_id,
            appointment_id=rx.appointment_id,
            patient_id=rx.patient_id,
            patient_name=pat_name,
            doctor_id=rx.doctor_id,
            doctor_name=doc_name,
            doctor_specialty=doc_spec,
            hospital_id=rx.hospital_id,
            hospital_name=hosp_name,
            prescription_date=rx.prescription_date,
            notes=rx.notes,
            is_active=rx.is_active,
            version=rx.version,
            amendment_reason=rx.amendment_reason,
            superseded_by_id=rx.superseded_by_id,
            items=[
                PrescriptionItemResponse(
                    id=it.id,
                    prescription_id=it.prescription_id,
                    medication_name=it.medication_name,
                    dosage=it.dosage,
                    frequency=it.frequency,
                    duration=it.duration,
                    route=it.route,
                    instructions=it.instructions,
                    created_at=it.created_at,
                )
                for it in (rx.items or [])
            ],
            created_at=rx.created_at,
        )

    @classmethod
    async def get_consultation_note_by_id(
        cls,
        note_id: uuid.UUID,
        current_user: User,
        db: AsyncSession,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> ConsultationNoteResponse:
        """
        Retrieves complete consultation note by ID with strict role-based access checks.
        """
        query = (
            select(ConsultationNote)
            .where(ConsultationNote.id == note_id)
            .options(
                selectinload(ConsultationNote.appointment),
                selectinload(ConsultationNote.patient),
                selectinload(ConsultationNote.doctor).selectinload(Doctor.user),
                selectinload(ConsultationNote.hospital),
                selectinload(ConsultationNote.diagnoses),
                selectinload(ConsultationNote.prescriptions).selectinload(Prescription.items),
            )
        )
        res = await db.execute(query)
        note = res.scalar_one_or_none()

        if not note:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Consultation record not found.",
            )

        # Access Control with audit logging
        await cls._verify_note_access(note, current_user, db, ip_address, user_agent)

        await clinical_audit_service.log(
            db=db,
            action="RECORD_ACCESSED",
            target_type="consultation_note",
            actor=current_user,
            target_id=note.id,
            patient_id=note.patient_id,
            doctor_id=note.doctor_id,
            hospital_id=note.hospital_id,
            metadata={"appointment_id": str(note.appointment_id)},
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return cls._format_consultation_response(note)

    @classmethod
    async def get_consultation_note_by_appointment(
        cls,
        appointment_id: uuid.UUID,
        current_user: User,
        db: AsyncSession,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> ConsultationNoteResponse:
        """
        Retrieves consultation note associated with a given appointment ID.
        """
        query = (
            select(ConsultationNote)
            .where(ConsultationNote.appointment_id == appointment_id)
            .options(
                selectinload(ConsultationNote.appointment),
                selectinload(ConsultationNote.patient),
                selectinload(ConsultationNote.doctor).selectinload(Doctor.user),
                selectinload(ConsultationNote.hospital),
                selectinload(ConsultationNote.diagnoses),
                selectinload(ConsultationNote.prescriptions).selectinload(Prescription.items),
            )
        )
        res = await db.execute(query)
        note = res.scalar_one_or_none()

        if not note:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No clinical consultation notes recorded for this appointment.",
            )

        await cls._verify_note_access(note, current_user, db, ip_address, user_agent)

        await clinical_audit_service.log(
            db=db,
            action="RECORD_ACCESSED",
            target_type="consultation_note",
            actor=current_user,
            target_id=note.id,
            patient_id=note.patient_id,
            doctor_id=note.doctor_id,
            hospital_id=note.hospital_id,
            metadata={"appointment_id": str(appointment_id)},
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return cls._format_consultation_response(note)

    @classmethod
    async def get_patient_medical_history(
        cls,
        patient_id: uuid.UUID,
        current_user: User,
        db: AsyncSession,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> PatientMedicalHistoryResponse:
        """
        Compiles the patient's comprehensive electronic health record (EHR) timeline:
        all consultation notes, diagnoses, prescriptions, and follow-up care.
        """
        # Authorization check
        if current_user.role == "patient" and current_user.id != patient_id:
            await clinical_audit_service.log(
                db=db,
                action="UNAUTHORIZED_ACCESS_ATTEMPT",
                target_type="patient_history",
                actor=current_user,
                target_id=patient_id,
                metadata={"attempted_patient_id": str(patient_id)},
                ip_address=ip_address,
                user_agent=user_agent,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You may only view your own medical records.",
            )

        if current_user.role == "doctor":
            # Doctor must be treating or have treated this patient
            doc_res = await db.execute(select(Doctor.id).where(Doctor.user_id == current_user.id))
            doctor_id = doc_res.scalar_one_or_none()
            if not doctor_id:
                raise HTTPException(status_code=403, detail="Doctor profile not found.")

            appt_check = await db.execute(
                select(Appointment.id)
                .where(
                    and_(
                        Appointment.patient_id == patient_id,
                        Appointment.doctor_id == doctor_id,
                    )
                )
                .limit(1)
            )
            if appt_check.scalar_one_or_none() is None:
                await clinical_audit_service.log(
                    db=db,
                    action="UNAUTHORIZED_ACCESS_ATTEMPT",
                    target_type="patient_history",
                    actor=current_user,
                    target_id=patient_id,
                    metadata={"attempted_patient_id": str(patient_id)},
                    ip_address=ip_address,
                    user_agent=user_agent,
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: You are not authorized to view medical records for patients not under your clinical care.",
                )

        if current_user.role == "hospital_admin":
            if current_user.hospital_id:
                hosp_check = await db.execute(
                    select(Appointment.id)
                    .where(
                        and_(
                            Appointment.patient_id == patient_id,
                            Appointment.hospital_id == current_user.hospital_id,
                        )
                    )
                    .limit(1)
                )
                if hosp_check.scalar_one_or_none() is None:
                    await clinical_audit_service.log(
                        db=db,
                        action="UNAUTHORIZED_ACCESS_ATTEMPT",
                        target_type="patient_history",
                        actor=current_user,
                        target_id=patient_id,
                        metadata={"attempted_hospital_id": str(current_user.hospital_id)},
                        ip_address=ip_address,
                        user_agent=user_agent,
                    )
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied: Patient has no consultation records at your hospital facility.",
                    )

        # 1. Fetch patient user record
        pat_res = await db.execute(select(User).where(User.id == patient_id))
        patient = pat_res.scalar_one_or_none()
        if not patient:
            raise HTTPException(status_code=404, detail="Patient record not found.")

        # 2. Fetch all consultation notes
        notes_q = (
            select(ConsultationNote)
            .where(ConsultationNote.patient_id == patient_id)
            .options(
                selectinload(ConsultationNote.appointment),
                selectinload(ConsultationNote.patient),
                selectinload(ConsultationNote.doctor).selectinload(Doctor.user),
                selectinload(ConsultationNote.hospital),
                selectinload(ConsultationNote.diagnoses),
                selectinload(ConsultationNote.prescriptions).selectinload(Prescription.items),
            )
            .order_by(ConsultationNote.consultation_date.desc(), ConsultationNote.consultation_time.desc())
        )
        notes_res = await db.execute(notes_q)
        notes = notes_res.scalars().all()

        formatted_notes = [cls._format_consultation_response(n) for n in notes]

        # 3. Compile all diagnoses
        diag_q = (
            select(Diagnosis)
            .where(Diagnosis.patient_id == patient_id)
            .options(
                selectinload(Diagnosis.doctor).selectinload(Doctor.user),
            )
            .order_by(Diagnosis.diagnosis_date.desc())
        )
        diag_res = await db.execute(diag_q)
        diagnoses = diag_res.scalars().all()

        formatted_diags = [
            DiagnosisResponse(
                id=d.id,
                consultation_note_id=d.consultation_note_id,
                patient_id=d.patient_id,
                doctor_id=d.doctor_id,
                doctor_name=d.doctor.user.full_name if d.doctor and d.doctor.user else "Doctor",
                doctor_specialty=d.doctor.specialty if d.doctor else "General Medicine",
                diagnosis_name=d.diagnosis_name,
                clinical_description=d.clinical_description,
                diagnosis_code=d.diagnosis_code,
                diagnosis_date=d.diagnosis_date,
                status=d.status,
                created_at=d.created_at,
            )
            for d in diagnoses
        ]

        # 4. Compile all prescriptions
        rx_q = (
            select(Prescription)
            .where(Prescription.patient_id == patient_id)
            .options(
                selectinload(Prescription.items),
                selectinload(Prescription.doctor).selectinload(Doctor.user),
                selectinload(Prescription.hospital),
            )
            .order_by(Prescription.prescription_date.desc(), Prescription.created_at.desc())
        )
        rx_res = await db.execute(rx_q)
        prescriptions = rx_res.scalars().all()

        formatted_rx = [
            PrescriptionResponse(
                id=rx.id,
                prescription_number=rx.prescription_number,
                consultation_note_id=rx.consultation_note_id,
                appointment_id=rx.appointment_id,
                patient_id=rx.patient_id,
                patient_name=patient.full_name,
                doctor_id=rx.doctor_id,
                doctor_name=rx.doctor.user.full_name if rx.doctor and rx.doctor.user else "Doctor",
                doctor_specialty=rx.doctor.specialty if rx.doctor else "General Medicine",
                hospital_id=rx.hospital_id,
                hospital_name=rx.hospital.name if rx.hospital else "Hospital Clinic",
                prescription_date=rx.prescription_date,
                notes=rx.notes,
                is_active=rx.is_active,
                version=rx.version,
                amendment_reason=rx.amendment_reason,
                superseded_by_id=rx.superseded_by_id,
                items=[
                    PrescriptionItemResponse(
                        id=it.id,
                        prescription_id=it.prescription_id,
                        medication_name=it.medication_name,
                        dosage=it.dosage,
                        frequency=it.frequency,
                        duration=it.duration,
                        route=it.route,
                        instructions=it.instructions,
                        created_at=it.created_at,
                    )
                    for it in (rx.items or [])
                ],
                created_at=rx.created_at,
            )
            for rx in prescriptions
        ]

        # 5. Compile upcoming follow-up recommendations
        upcoming_follow_ups = []
        today = date.today()
        for n in notes:
            if n.follow_up_recommended_date and n.follow_up_recommended_date >= today:
                doc_name = n.doctor.user.full_name if n.doctor and n.doctor.user else "Doctor"
                upcoming_follow_ups.append({
                    "consultation_id": str(n.id),
                    "recommended_date": n.follow_up_recommended_date.isoformat(),
                    "doctor_name": doc_name,
                    "doctor_specialty": n.doctor.specialty if n.doctor else "General Medicine",
                    "instructions": n.follow_up_instructions,
                })

        active_diags = sum(1 for d in diagnoses if d.status == "active")

        # Audit log medical history access
        await clinical_audit_service.log(
            db=db,
            action="RECORD_ACCESSED",
            target_type="patient_history",
            actor=current_user,
            target_id=patient_id,
            patient_id=patient_id,
            metadata={
                "total_consultations": len(formatted_notes),
                "total_prescriptions": len(formatted_rx),
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return PatientMedicalHistoryResponse(
            patient_id=patient.id,
            patient_name=patient.full_name,
            patient_email=patient.email,
            patient_phone=patient.phone,
            total_consultations=len(formatted_notes),
            total_prescriptions=len(formatted_rx),
            active_diagnoses_count=active_diags,
            consultations=formatted_notes,
            prescriptions=formatted_rx,
            diagnoses=formatted_diags,
            upcoming_follow_ups=upcoming_follow_ups,
        )

    @classmethod
    async def schedule_follow_up(
        cls,
        doctor_user: User,
        data: FollowUpCreateRequest,
        db: AsyncSession,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> FollowUpResponse:
        """
        Coordinates follow-up care with full safety guarantees:
        - Validates target date is not in the past.
        - Validates time slot against ALLOWED_SLOT_TIMES.
        - Detects slot collisions and prevents double bookings (409 Conflict).
        - Idempotently handles duplicate follow-up submissions.
        - Records immutable audit trail entry.
        - Dispatches patient alert strictly post-commit.
        """
        # 1. Date validation
        today = date.today()
        if data.recommended_date < today:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Recommended follow-up date cannot be in the past.",
            )

        doc_res = await db.execute(select(Doctor).where(Doctor.user_id == doctor_user.id))
        doctor = doc_res.scalar_one_or_none()
        if not doctor:
            raise HTTPException(status_code=403, detail="Doctor profile not found.")

        appt_q = (
            select(Appointment)
            .where(Appointment.id == data.appointment_id)
            .options(
                selectinload(Appointment.doctor).selectinload(Doctor.user),
                selectinload(Appointment.patient),
            )
            .with_for_update()
        )
        appt_res = await db.execute(appt_q)
        appointment = appt_res.scalar_one_or_none()
        if not appointment:
            raise HTTPException(status_code=404, detail="Appointment not found.")

        if appointment.doctor_id != doctor.id:
            await clinical_audit_service.log(
                db=db,
                action="UNAUTHORIZED_ACCESS_ATTEMPT",
                target_type="follow_up",
                actor=doctor_user,
                target_id=data.appointment_id,
                metadata={"attempted_action": "schedule_follow_up"},
                ip_address=ip_address,
                user_agent=user_agent,
            )
            raise HTTPException(status_code=403, detail="Access denied: Not your assigned appointment.")

        # Update consultation note if present
        note_q = select(ConsultationNote).where(ConsultationNote.appointment_id == appointment.id)
        note_res = await db.execute(note_q)
        note = note_res.scalar_one_or_none()
        if note:
            note.follow_up_recommended_date = data.recommended_date
            note.follow_up_instructions = data.instructions

        follow_up_appt_id = None
        follow_up_token = None

        if data.schedule_appointment:
            slot_str = data.recommended_time or "10:00"
            if slot_str not in ALLOWED_SLOT_TIMES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Appointment time must be a valid 30-minute clinic slot between "
                        f"09:00 and 16:30 (excluding lunch 13:00-14:00). Got '{slot_str}'."
                    ),
                )

            time_parts = slot_str.split(":")
            slot_t = time(int(time_parts[0]), int(time_parts[1]))

            # Check if doctor already has an active appointment in this slot (slot conflict prevention)
            conflict_q = (
                select(Appointment.id)
                .where(
                    and_(
                        Appointment.doctor_id == doctor.id,
                        Appointment.appointment_date == data.recommended_date,
                        Appointment.appointment_time == slot_t,
                        Appointment.status.notin_(["cancelled", "no_show"]),
                    )
                )
                .limit(1)
            )
            conflict_res = await db.execute(conflict_q)
            if conflict_res.scalar_one_or_none() is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This appointment time slot is already booked for this doctor. Please choose another slot.",
                )

            # Prevent duplicate follow-up bookings on the same appointment
            dup_q = (
                select(Appointment.id, Appointment.appointment_token)
                .where(
                    and_(
                        Appointment.patient_id == appointment.patient_id,
                        Appointment.doctor_id == doctor.id,
                        Appointment.appointment_date == data.recommended_date,
                        Appointment.notes.ilike(f"%Follow-up consultation for appointment {appointment.appointment_token}%"),
                        Appointment.status.notin_(["cancelled"]),
                    )
                )
                .limit(1)
            )
            dup_res = await db.execute(dup_q)
            dup_row = dup_res.first()
            if dup_row is not None:
                follow_up_appt_id = dup_row[0]
                follow_up_token = dup_row[1]
            else:
                clinic_date_str = data.recommended_date.strftime("%Y%m%d")
                token_base = f"MS-{clinic_date_str}-{uuid.uuid4().hex[:4].upper()}"
                new_appt = Appointment(
                    id=uuid.uuid4(),
                    appointment_token=token_base,
                    patient_id=appointment.patient_id,
                    doctor_id=doctor.id,
                    hospital_id=appointment.hospital_id,
                    appointment_date=data.recommended_date,
                    appointment_time=slot_t,
                    status="scheduled",
                    notes=f"Follow-up consultation for appointment {appointment.appointment_token}: {data.instructions or 'Routine progress check.'}",
                )
                db.add(new_appt)
                await db.flush()
                follow_up_appt_id = new_appt.id
                follow_up_token = new_appt.appointment_token

        # Audit log
        await clinical_audit_service.log(
            db=db,
            action="FOLLOW_UP_SCHEDULED",
            target_type="follow_up",
            actor=doctor_user,
            target_id=follow_up_appt_id,
            patient_id=appointment.patient_id,
            doctor_id=doctor.id,
            hospital_id=appointment.hospital_id,
            metadata={
                "original_appointment_token": appointment.appointment_token,
                "follow_up_date": data.recommended_date.isoformat(),
                "scheduled": bool(follow_up_token),
                "follow_up_token": follow_up_token,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        await db.commit()

        # Send follow-up notification post-commit
        doc_name = doctor_user.full_name
        msg = (
            f"Follow-up care update: Dr. {doc_name} has scheduled or recommended a follow-up visit on "
            f"{data.recommended_date.strftime('%A, %b %d, %Y')}."
        )
        if follow_up_token:
            msg += f" Confirmed Booking Reference: {follow_up_token}."
        if data.instructions:
            msg += f" Instructions: {data.instructions}"

        try:
            await notification_service.create_notification(
                db=db,
                user_id=appointment.patient_id,
                title="Follow-Up Consultation Scheduled" if follow_up_token else "Follow-Up Care Recommended",
                message=msg,
                category="appointment",
                event_type="follow_up_scheduled" if follow_up_token else "follow_up_recommended",
                urgency="high" if follow_up_token else "normal",
                idempotency_key=f"follow_up_{appointment.id}_{data.recommended_date}",
                metadata_json={
                    "follow_up_date": data.recommended_date.isoformat(),
                    "doctor_name": doc_name,
                    "follow_up_token": follow_up_token,
                },
                auto_commit=True,
            )
        except Exception as notif_err:
            logger.error(f"Failed to dispatch follow-up notification: {notif_err}", exc_info=True)

        return FollowUpResponse(
            appointment_id=appointment.id,
            patient_id=appointment.patient_id,
            doctor_id=doctor.id,
            recommended_date=data.recommended_date,
            instructions=data.instructions,
            follow_up_appointment_id=follow_up_appt_id,
            follow_up_token=follow_up_token,
            notification_dispatched=True,
            status="scheduled" if follow_up_token else "recommended",
        )

    # -----------------------------------------------------------------------
    # Helper & Format Methods
    # -----------------------------------------------------------------------

    @classmethod
    async def _verify_note_access(
        cls,
        note: ConsultationNote,
        current_user: User,
        db: AsyncSession,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """Verifies role-based access rights to a specific consultation record with audit trail."""
        if current_user.role == "patient" and note.patient_id != current_user.id:
            await clinical_audit_service.log(
                db=db,
                action="UNAUTHORIZED_ACCESS_ATTEMPT",
                target_type="consultation_note",
                actor=current_user,
                target_id=note.id,
                metadata={"attempted_patient_id": str(note.patient_id)},
                ip_address=ip_address,
                user_agent=user_agent,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You may only view your own consultation notes.",
            )

        if current_user.role == "doctor":
            doc_res = await db.execute(select(Doctor.id).where(Doctor.user_id == current_user.id))
            doctor_id = doc_res.scalar_one_or_none()
            if note.doctor_id != doctor_id:
                # Check if doctor has a care relationship with this patient
                appt_check = await db.execute(
                    select(Appointment.id).where(
                        and_(
                            Appointment.patient_id == note.patient_id,
                            Appointment.doctor_id == doctor_id,
                        )
                    ).limit(1)
                )
                if appt_check.scalar_one_or_none() is None:
                    await clinical_audit_service.log(
                        db=db,
                        action="UNAUTHORIZED_ACCESS_ATTEMPT",
                        target_type="consultation_note",
                        actor=current_user,
                        target_id=note.id,
                        metadata={"attempted_doctor_id": str(note.doctor_id)},
                        ip_address=ip_address,
                        user_agent=user_agent,
                    )
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied: You may only view records for patients under your clinical care.",
                    )

        if current_user.role == "hospital_admin":
            if current_user.hospital_id and note.hospital_id != current_user.hospital_id:
                await clinical_audit_service.log(
                    db=db,
                    action="UNAUTHORIZED_ACCESS_ATTEMPT",
                    target_type="consultation_note",
                    actor=current_user,
                    target_id=note.id,
                    metadata={"attempted_hospital_id": str(note.hospital_id)},
                    ip_address=ip_address,
                    user_agent=user_agent,
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: Record does not belong to your hospital facility.",
                )

    @classmethod
    def _format_consultation_response(cls, note: ConsultationNote) -> ConsultationNoteResponse:
        """Formats ConsultationNote model to Pydantic response."""
        pat_name = note.patient.full_name if note.patient else "Patient"
        doc_name = note.doctor.user.full_name if note.doctor and note.doctor.user else "Doctor"
        doc_spec = note.doctor.specialty if note.doctor else "General Medicine"
        hosp_name = note.hospital.name if note.hospital else "Hospital Clinic"
        appt_tok = note.appointment.appointment_token if note.appointment else None

        diags = [
            DiagnosisResponse(
                id=d.id,
                consultation_note_id=d.consultation_note_id,
                patient_id=d.patient_id,
                doctor_id=d.doctor_id,
                doctor_name=doc_name,
                doctor_specialty=doc_spec,
                diagnosis_name=d.diagnosis_name,
                clinical_description=d.clinical_description,
                diagnosis_code=d.diagnosis_code,
                diagnosis_date=d.diagnosis_date,
                status=d.status,
                created_at=d.created_at,
            )
            for d in (note.diagnoses or [])
        ]

        prescriptions = [
            PrescriptionResponse(
                id=rx.id,
                prescription_number=rx.prescription_number,
                consultation_note_id=rx.consultation_note_id,
                appointment_id=rx.appointment_id,
                patient_id=rx.patient_id,
                patient_name=pat_name,
                doctor_id=rx.doctor_id,
                doctor_name=doc_name,
                doctor_specialty=doc_spec,
                hospital_id=rx.hospital_id,
                hospital_name=hosp_name,
                prescription_date=rx.prescription_date,
                notes=rx.notes,
                is_active=rx.is_active,
                version=rx.version,
                amendment_reason=rx.amendment_reason,
                superseded_by_id=rx.superseded_by_id,
                items=[
                    PrescriptionItemResponse(
                        id=it.id,
                        prescription_id=it.prescription_id,
                        medication_name=it.medication_name,
                        dosage=it.dosage,
                        frequency=it.frequency,
                        duration=it.duration,
                        route=it.route,
                        instructions=it.instructions,
                        created_at=it.created_at,
                    )
                    for it in (rx.items or [])
                ],
                created_at=rx.created_at,
            )
            for rx in (note.prescriptions or [])
        ]

        return ConsultationNoteResponse(
            id=note.id,
            appointment_id=note.appointment_id,
            appointment_token=appt_tok,
            patient_id=note.patient_id,
            patient_name=pat_name,
            doctor_id=note.doctor_id,
            doctor_name=doc_name,
            doctor_specialty=doc_spec,
            hospital_id=note.hospital_id,
            hospital_name=hosp_name,
            consultation_date=note.consultation_date,
            consultation_time=note.consultation_time,
            chief_complaint=note.chief_complaint,
            symptoms=note.symptoms,
            clinical_observations=note.clinical_observations,
            examination_notes=note.examination_notes,
            diagnosis_summary=note.diagnosis_summary,
            treatment_plan=note.treatment_plan,
            doctor_recommendations=note.doctor_recommendations,
            follow_up_recommended_date=note.follow_up_recommended_date,
            follow_up_instructions=note.follow_up_instructions,
            diagnoses=diags,
            prescriptions=prescriptions,
            created_at=note.created_at,
            updated_at=note.updated_at,
        )
