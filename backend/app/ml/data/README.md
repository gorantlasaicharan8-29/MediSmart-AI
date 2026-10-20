# MediSmart ML Datasets (SYNTHETIC)

> **IMPORTANT NOTICE**:
> All datasets in this directory (`waiting_time_dataset.csv` and `noshow_dataset.csv`) are **100% SYNTHETIC**, generated exclusively for development, training, and testing of machine learning pipelines within MediSmart.
> - **Zero** real patient names, contacts, or clinical records are used.
> - **Zero** records originate from actual hospital operations or clinical observations.
> - These datasets are maintained **strictly outside the live PostgreSQL database (`medismart_db`)**.

---

## 1. Waiting-Time Regression Dataset (`waiting_time_dataset.csv`)

### Purpose
Used to train regression models predicting patient wait time (elapsed minutes between digital check-in and being called into the doctor's consultation room).

### Observation Unit
A single completed patient queue check-in event.

### Features Visible at Prediction Time (Check-In)
| Feature Name | Type | Unit | Description | Range |
| :--- | :--- | :--- | :--- | :--- |
| `doctor_id` | string | UUID | Synthetic identifier of the consulting doctor | Categorical |
| `doctor_specialty` | string | category | Clinical department (Cardiology, Orthopedics, etc.) | 10 Specialties |
| `doctor_experience_years` | int | years | Doctor clinical seniority | 1 – 40 |
| `hospital_id` | string | UUID | Synthetic identifier of the hospital facility | Categorical |
| `day_of_week` | int | index | Day of visit (0=Monday, 6=Sunday) | 0 – 6 |
| `slot_hour` | int | hour | Scheduled slot hour | 9 – 16 |
| `slot_minute` | int | minute | Scheduled slot minute | 0, 30 |
| `arrival_lead_minutes` | float | minutes | Patient arrival offset relative to slot (+ early, - late) | -60.0 – 60.0 |
| `queue_position_at_checkin`| int | rank | Queue position assigned upon check-in | $\ge 1$ |
| `patients_waiting_ahead` | int | count | Number of unserved patients ahead in queue | $\ge 0$ |
| `is_doctor_active_consultation` | int | binary | 1 if doctor currently has an active patient, else 0 | 0, 1 |
| `historical_avg_consultation_minutes` | float | minutes | Historical doctor/specialty average duration | 8.0 – 35.0 |
| `is_synthetic` | bool | boolean | Constant flag confirming synthetic provenance | `True` |

### Target Variable
- **`actual_wait_minutes`** (float, minutes, $\ge 0.0$):
  $$\text{actual\_wait\_minutes} = \frac{\text{called\_at} - \text{checked\_in\_at}}{60 \text{ seconds}}$$

### Target Leakage Prevention
Post-call timestamps (`called_at`, `completed_at`), actual consultation duration, and subsequent patient arrivals are strictly excluded from input features.

---

## 2. No-Show Classification Dataset (`noshow_dataset.csv`)

### Purpose
Used to train classification models estimating the probability that a booked appointment will result in an unexcused absence (no-show).

### Observation Unit
A single scheduled appointment.

### Features Visible at Prediction Time (Booking Time)
| Feature Name | Type | Unit | Description | Range |
| :--- | :--- | :--- | :--- | :--- |
| `appointment_id` | string | UUID | Synthetic appointment identifier | Categorical |
| `patient_id` | string | UUID | Synthetic patient identifier | Categorical |
| `lead_time_days` | int | days | Days between booking date and appointment date | 0 – 60 |
| `day_of_week` | int | index | Day of appointment (0=Monday, 6=Sunday) | 0 – 6 |
| `slot_hour` | int | hour | Scheduled appointment hour | 9 – 16 |
| `is_weekend` | int | binary | 1 if Saturday or Sunday, else 0 | 0, 1 |
| `doctor_specialty` | string | category | Clinical department | 10 Specialties |
| `consultation_fee` | float | INR | Out-of-pocket consultation fee | 300.0 – 2000.0 |
| `patient_prior_appointments` | int | count | Prior appointments booked by this patient before this date | $\ge 0$ |
| `patient_prior_no_shows` | int | count | Prior no-shows for this patient before this date | $\ge 0$ |
| `patient_prior_no_show_rate` | float | ratio | Ratio of prior no-shows to prior appointments | 0.0 – 1.0 |
| `has_notes` | int | binary | 1 if patient submitted booking notes/symptoms | 0, 1 |
| `is_synthetic` | bool | boolean | Constant flag confirming synthetic provenance | `True` |

### Target Variable
- **`is_no_show`** (int, binary $\in \{0, 1\}$):
  - `1`: Patient failed to appear (no-show).
  - `0`: Patient attended appointment (`checked_in`, `in_progress`, or `completed`).
- *Note on Cancellations*: Advance cancellations prior to appointment day are excluded from no-show evaluation targets.

### Temporal Integrity & Leakage Prevention
Patient historical features (`patient_prior_no_shows`) are computed strictly using past appointments where $\text{appointment\_date} < \text{current\_appointment\_date}$ in strict chronological sequence.
