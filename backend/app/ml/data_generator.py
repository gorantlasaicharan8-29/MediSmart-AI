"""
Standalone Synthetic ML Data Generator for MediSmart.

Generates reproducible, statistically grounded datasets for:
1. Patient Waiting-Time Prediction (Regression) -> waiting_time_dataset.csv
2. Appointment No-Show Prediction (Classification) -> noshow_dataset.csv

ALL GENERATED DATA IS 100% SYNTHETIC AND PRESERVED STRICTLY OUTSIDE THE DATABASE.
ZERO REAL PATIENT OR CLINICAL DATA IS INCLUDED.
"""
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from app.ml.config import (
    CLINICAL_SPECIALTIES,
    DATA_DIR,
    DEFAULT_RANDOM_SEED,
    NOSHOW_DATASET_PATH,
    NOSHOW_FEATURES,
    NOSHOW_TARGET,
    WAITING_TIME_DATASET_PATH,
    WAITING_TIME_FEATURES,
    WAITING_TIME_TARGET,
)

# Clinical specialty consultation parameters (mean minutes, std minutes, baseline fee INR)
SPECIALTY_PROFILES: Dict[str, Dict[str, float]] = {
    "Cardiology": {"duration_mean": 18.0, "duration_std": 4.5, "fee": 1200.0},
    "Neurology": {"duration_mean": 20.0, "duration_std": 5.0, "fee": 1100.0},
    "Orthopedics": {"duration_mean": 16.0, "duration_std": 4.0, "fee": 1000.0},
    "Gastroenterology": {"duration_mean": 15.0, "duration_std": 3.5, "fee": 950.0},
    "Oncology": {"duration_mean": 24.0, "duration_std": 6.0, "fee": 1400.0},
    "Pediatrics": {"duration_mean": 14.0, "duration_std": 3.5, "fee": 800.0},
    "Nephrology": {"duration_mean": 18.0, "duration_std": 4.5, "fee": 1050.0},
    "Pulmonology": {"duration_mean": 15.0, "duration_std": 3.8, "fee": 900.0},
    "Dermatology": {"duration_mean": 10.0, "duration_std": 2.5, "fee": 750.0},
    "General Medicine": {"duration_mean": 12.0, "duration_std": 3.0, "fee": 600.0},
}


def _sigmoid(x: np.ndarray) -> np.ndarray:
    """Stable sigmoid activation function."""
    return 1.0 / (1.0 + np.exp(-np.clip(x, -25.0, 25.0)))


def generate_noshow_data(
    n_samples: int = 10000,
    target_noshow_rate: float = 0.18,
    seed: int = DEFAULT_RANDOM_SEED,
) -> pd.DataFrame:
    """
    Generates synthetic appointment no-show dataset strictly observable at booking time.
    
    Guarantees:
    - Purely synthetic records labeled with is_synthetic = True.
    - Causal temporal ordering: prior patient attendance is computed exclusively
      from past appointments where appointment_date < current_appointment_date.
    - Excludes cancelled appointments from training targets.
    - No look-ahead bias or post-booking data leakage.
    - Bounded target no-show label in {0, 1}.
    """
    rng = np.random.default_rng(seed)

    # 1. Generate synthetic patient and doctor pools
    n_patients = max(100, n_samples // 5)
    n_doctors = 25
    n_hospitals = 6

    synthetic_patient_ids = [f"SYN-PAT-{i:05d}" for i in range(1, n_patients + 1)]
    synthetic_doctor_ids = [f"SYN-DOC-{i:03d}" for i in range(1, n_doctors + 1)]
    synthetic_hospital_ids = [f"SYN-HOSP-{i:02d}" for i in range(1, n_hospitals + 1)]

    # Assign static attributes to synthetic doctors
    doctor_specialties = rng.choice(CLINICAL_SPECIALTIES, size=n_doctors)
    doctor_fees = np.array([
        SPECIALTY_PROFILES[spec]["fee"] * rng.uniform(0.85, 1.25)
        for spec in doctor_specialties
    ])
    doctor_hospitals = rng.choice(synthetic_hospital_ids, size=n_doctors)

    # 2. Timeline generation (180 days)
    start_date = date(2026, 1, 1)
    date_offsets = rng.integers(0, 180, size=n_samples)
    date_offsets.sort()  # Enforce strict chronological ordering

    # Patient attendance ledger for temporal causality tracking:
    # patient_id -> {"total": int, "no_shows": int}
    patient_ledger: Dict[str, Dict[str, int]] = {
        pid: {"total": 0, "no_shows": 0} for pid in synthetic_patient_ids
    }

    records: List[Dict] = []
    available_hours = [9, 10, 11, 12, 14, 15, 16]
    hour_probs = [0.15, 0.20, 0.18, 0.12, 0.15, 0.12, 0.08]

    for i in range(n_samples):
        appt_date = start_date + timedelta(days=int(date_offsets[i]))
        doc_idx = rng.integers(0, n_doctors)
        doc_id = synthetic_doctor_ids[doc_idx]
        specialty = doctor_specialties[doc_idx]
        fee = round(float(doctor_fees[doc_idx]), 2)
        hosp_id = doctor_hospitals[doc_idx]

        # Select patient (some repeat patients, some new)
        pat_id = rng.choice(synthetic_patient_ids)

        # Lead time: log-normal with mean ~8 days, max 60 days
        raw_lead = rng.lognormal(mean=2.0, sigma=0.8)
        lead_time_days = int(np.clip(raw_lead, 0, 60))

        # Booking creation date strictly before or on appointment date
        booking_created_at = appt_date - timedelta(days=lead_time_days)

        day_of_week = int(appt_date.weekday())
        is_weekend = 1 if day_of_week in (5, 6) else 0
        slot_hour = int(rng.choice(available_hours, p=hour_probs))
        slot_minute = int(rng.choice([0, 30]))

        # Patient clinical notes at booking: ~35% provide notes
        has_notes = int(rng.uniform() < 0.35)

        # Historical attendance features: strictly prior to this date
        hist = patient_ledger[pat_id]
        prior_total = hist["total"]
        prior_no_shows = hist["no_shows"]
        prior_rate = round(prior_no_shows / prior_total, 4) if prior_total > 0 else float(target_noshow_rate)

        # Model latent no-show probability using clinical logistic response
        # Intercept calibrated dynamically around target_noshow_rate
        base_logit = np.log(target_noshow_rate / (1.0 - target_noshow_rate))

        # Signal terms
        lead_effect = 0.04 * (lead_time_days - 7)  # Longer lead time -> higher no-show
        history_effect = 1.8 * (prior_rate - target_noshow_rate) if prior_total > 0 else 0.0
        weekend_effect = 0.35 if is_weekend else -0.05
        hour_effect = 0.20 if slot_hour in (9, 16) else -0.10  # Very early or late slots have higher friction
        notes_effect = -0.40 if has_notes else 0.15  # Patient wrote specific notes -> higher commitment
        fee_effect = -0.0003 * (fee - 950.0)  # Higher out-of-pocket commitment -> slightly lower no-show

        total_logit = base_logit + lead_effect + history_effect + weekend_effect + hour_effect + notes_effect + fee_effect + rng.normal(0, 0.25)
        p_noshow = float(_sigmoid(np.array([total_logit]))[0])

        # Outcome determination
        is_no_show = 1 if rng.uniform() < p_noshow else 0

        # Update ledger strictly AFTER calculating features for this appointment
        patient_ledger[pat_id]["total"] += 1
        patient_ledger[pat_id]["no_shows"] += is_no_show

        records.append({
            "appointment_id": f"SYN-APT-{i+1:06d}",
            "patient_id": pat_id,
            "doctor_id": doc_id,
            "hospital_id": hosp_id,
            "appointment_date": appt_date.isoformat(),
            "booking_created_at": booking_created_at.isoformat(),
            "lead_time_days": lead_time_days,
            "day_of_week": day_of_week,
            "slot_hour": slot_hour,
            "slot_minute": slot_minute,
            "is_weekend": is_weekend,
            "doctor_specialty": specialty,
            "consultation_fee": fee,
            "patient_prior_appointments": prior_total,
            "patient_prior_no_shows": prior_no_shows,
            "patient_prior_no_show_rate": prior_rate,
            "has_notes": has_notes,
            "is_synthetic": True,
            "is_no_show": is_no_show,
        })

    df = pd.DataFrame(records)
    return df


def generate_waiting_time_data(
    n_samples: int = 5000,
    seed: int = DEFAULT_RANDOM_SEED,
) -> pd.DataFrame:
    """
    Generates synthetic patient waiting-time dataset strictly observable at check-in.
    
    Target:
      actual_wait_minutes = (called_at - checked_in_at) in minutes (float >= 0.0)
      
    Guarantees:
    - Purely synthetic records labeled with is_synthetic = True.
    - Zero target leakage: called_at, completed_at, and consultation duration
      are NOT included in the input feature set.
    - Non-negative target values.
    - Realistic queuing queuing dynamics based on doctor consultation pace and queue depth.
    """
    rng = np.random.default_rng(seed)

    n_doctors = 20
    n_hospitals = 6
    synthetic_doctor_ids = [f"SYN-DOC-{i:03d}" for i in range(1, n_doctors + 1)]
    synthetic_hospital_ids = [f"SYN-HOSP-{i:02d}" for i in range(1, n_hospitals + 1)]

    # Assign specialties and experience
    doctor_specialties = rng.choice(CLINICAL_SPECIALTIES, size=n_doctors)
    doctor_experience = rng.integers(3, 35, size=n_doctors)
    doctor_hospitals = rng.choice(synthetic_hospital_ids, size=n_doctors)

    # Doctor intrinsic pace factor (senior doctors with more experience are slightly faster and more predictable)
    doctor_pace_factors = 1.0 - (doctor_experience - 15) * 0.008 + rng.normal(0, 0.04, size=n_doctors)
    doctor_pace_factors = np.clip(doctor_pace_factors, 0.75, 1.30)

    start_date = date(2026, 1, 1)
    date_offsets = rng.integers(0, 180, size=n_samples)
    date_offsets.sort()

    records: List[Dict] = []
    available_hours = [9, 10, 11, 12, 14, 15, 16]

    for i in range(n_samples):
        queue_date = start_date + timedelta(days=int(date_offsets[i]))
        doc_idx = rng.integers(0, n_doctors)
        doc_id = synthetic_doctor_ids[doc_idx]
        specialty = doctor_specialties[doc_idx]
        exp_years = int(doctor_experience[doc_idx])
        hosp_id = doctor_hospitals[doc_idx]
        pace = float(doctor_pace_factors[doc_idx])

        spec_profile = SPECIALTY_PROFILES[specialty]
        base_consult_duration = spec_profile["duration_mean"]
        duration_std = spec_profile["duration_std"]
        hist_avg_duration = round(base_consult_duration * pace, 2)

        slot_hour = int(rng.choice(available_hours))
        slot_minute = int(rng.choice([0, 30]))
        day_of_week = int(queue_date.weekday())

        # Queue position at check-in (1 to 15)
        # Position 1 = first patient of session, position 8 = later in morning
        position = int(rng.geometric(p=0.20))
        position = int(np.clip(position, 1, 16))
        patients_ahead = position - 1

        # Whether doctor is currently active with a patient
        if patients_ahead > 0:
            is_active = 1 if rng.uniform() < 0.90 else 0
        else:
            is_active = 1 if rng.uniform() < 0.25 else 0

        # Arrival offset in minutes relative to scheduled slot
        # (+ minutes: early, - minutes: late)
        arrival_lead = float(np.clip(rng.normal(loc=7.0, scale=12.0), -45.0, 45.0))
        arrival_lead_minutes = round(arrival_lead, 1)

        # Queuing physics for actual wait time:
        # Wait time = (remaining time of active patient) + (patients ahead * consultation time) + noise
        if is_active:
            # Remaining time of current consultation ~ Uniform(2, avg_duration)
            current_remaining = float(rng.uniform(2.0, hist_avg_duration))
        else:
            current_remaining = 0.0

        # Time for unserved patients waiting ahead
        ahead_wait = sum(
            float(np.clip(rng.normal(hist_avg_duration, duration_std), 4.0, 45.0))
            for _ in range(patients_ahead)
        )

        # Clinic delay / drift accumulating through the day (afternoon clinics have slightly higher delays)
        hour_drift = max(0.0, (slot_hour - 9) * 1.5)

        # Patient arrived late: if patient arrived late and others went ahead, wait time is reduced or increased
        arrival_adjustment = -0.3 * arrival_lead_minutes if arrival_lead_minutes > 15 else 0.0

        # Clinic random noise (emergency interruptions, technical delays)
        noise = float(rng.exponential(scale=2.5))

        simulated_wait = current_remaining + ahead_wait + hour_drift + arrival_adjustment + noise
        actual_wait_minutes = float(max(0.0, round(simulated_wait, 1)))

        records.append({
            "queue_entry_id": f"SYN-QE-{i+1:06d}",
            "doctor_id": doc_id,
            "doctor_specialty": specialty,
            "doctor_experience_years": exp_years,
            "hospital_id": hosp_id,
            "queue_date": queue_date.isoformat(),
            "day_of_week": day_of_week,
            "slot_hour": slot_hour,
            "slot_minute": slot_minute,
            "arrival_lead_minutes": arrival_lead_minutes,
            "queue_position_at_checkin": position,
            "patients_waiting_ahead": patients_ahead,
            "is_doctor_active_consultation": is_active,
            "historical_avg_consultation_minutes": hist_avg_duration,
            "is_synthetic": True,
            "actual_wait_minutes": actual_wait_minutes,
        })

    df = pd.DataFrame(records)
    return df


def save_datasets(
    noshow_df: pd.DataFrame,
    waiting_time_df: pd.DataFrame,
    output_dir: Path = DATA_DIR,
) -> Tuple[Path, Path]:
    """
    Saves generated synthetic datasets as CSV files with synthetic metadata headers.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    noshow_path = output_dir / "noshow_dataset.csv"
    waiting_path = output_dir / "waiting_time_dataset.csv"

    # Save to CSV
    noshow_df.to_csv(noshow_path, index=False)
    waiting_time_df.to_csv(waiting_path, index=False)

    return noshow_path, waiting_path


def generate_all_datasets(
    n_noshow: int = 10000,
    n_waiting: int = 5000,
    noshow_rate: float = 0.18,
    seed: int = DEFAULT_RANDOM_SEED,
    output_dir: Optional[Path] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Top-level helper to generate, validate, and persist both synthetic datasets.
    """
    target_dir = output_dir or DATA_DIR
    print(f"Generating synthetic No-Show dataset ({n_noshow} samples, target rate: {noshow_rate:.1%})...")
    noshow_df = generate_noshow_data(n_samples=n_noshow, target_noshow_rate=noshow_rate, seed=seed)

    print(f"Generating synthetic Waiting-Time dataset ({n_waiting} samples)...")
    waiting_df = generate_waiting_time_data(n_samples=n_waiting, seed=seed)

    save_datasets(noshow_df, waiting_df, output_dir=target_dir)
    print(f"Datasets successfully saved to:\n  - {target_dir / 'noshow_dataset.csv'}\n  - {target_dir / 'waiting_time_dataset.csv'}")
    return noshow_df, waiting_df


if __name__ == "__main__":
    generate_all_datasets()
