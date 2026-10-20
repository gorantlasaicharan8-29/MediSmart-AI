---
phase: 6
plan: 1
wave: 1
gap_closure: false
---

# Plan 6.1: ML Dataset Design & Feature Engineering Architecture

## Objective
Establish a reliable, explainable, and scientifically sound machine learning foundation for:
1. **Patient Waiting-Time Prediction** (Regression: minutes from check-in to doctor call).
2. **Appointment No-Show Prediction** (Binary Classification: probability a booked appointment results in a no-show).

This plan defines the feature definitions, temporal alignment, data leakage safeguards, chronological evaluation strategy, synthetic dataset generation specifications, and modular service architecture. **No training records, model training, or database schema modifications are executed during this plan.**

---

## 1. Context & Baseline Inventory

### 1.1 Active Database State (`medismart_db`)
- **Alembic Revision**: `63b2c1f9d5e2`
- **Current Records**:
  - `hospitals`: 8 facilities (real OpenStreetMap coordinates, verified specialties/facilities).
  - `doctors`: 10 doctors across cardiology, neurology, orthopedics, gastroenterology, oncology, pediatrics, nephrology, pulmonology, and dermatology.
  - `users`: 10 users (patients, doctors, administrators).
  - `appointments`: 0 historical rows.
  - `queue_entries`: 0 historical rows.
- **Data Availability Reality**:
  - Zero historical patient visits, consultation durations, call timestamps, or attendance outcomes exist in `medismart_db` or `medismart_test_db`.
  - Machine learning models cannot be trained on the current database without generating statistically grounded, realistic synthetic clinical workflow datasets.
  - Per project constraints: All synthetic training data must be explicitly labeled as synthetic; no synthetic data will be commingled with active operational tables in `medismart_db`.

### 1.2 Clinical & Queue Lifecycle Grounding
```
[Appointment Scheduled]
  │  Features observable: lead time, slot time, doctor specialty, fee, patient prior attendance
  │
  ├────────────────────────────────────────► [Prediction Point A: No-Show Classification]
  │                                           Target: is_no_show ∈ {0, 1}
  │
[Patient Check-In] (Status -> 'checked_in')
  │  Features observable: arrival lead minutes, queue position, patients ahead, doctor pace
  │
  ├────────────────────────────────────────► [Prediction Point B: Waiting-Time Regression]
  │                                           Target: actual_wait_minutes (checked_in_at to called_at)
  │
[Doctor Calls Patient] (Status -> 'in_consultation')
  │  called_at timestamp recorded
  │
[Doctor Completes Consultation] (Status -> 'completed')
     completed_at timestamp recorded
```

---

## 2. Dataset & Target Design

### 2.1 Dataset A: Patient Waiting-Time Regression (`waiting_time_dataset`)
- **Unit of Observation**: A checked-in queue entry that was called for consultation.
- **Prediction Moment**: At patient check-in (`POST /api/v1/queue/check-in`) or upon dynamic queue status check (`GET /api/v1/queue/my`).
- **Target Variable**:
  - `actual_wait_minutes` (Float, continuous, $\ge 0.0$):
    $$\text{actual\_wait\_minutes} = \frac{\text{called\_at} - \text{checked\_in\_at}}{60 \text{ seconds}}$$
- **Input Features (Observable strictly at prediction moment)**:
  1. `doctor_id` (Categorical UUID): Doctor identifier.
  2. `doctor_specialty` (Categorical String): E.g., Cardiology, Orthopedics, Pediatrics (affects procedure pace).
  3. `doctor_experience_years` (Integer): Clinical seniority.
  4. `hospital_id` (Categorical UUID): Facility identifier.
  5. `day_of_week` (Integer: 0=Monday, 6=Sunday): Captures day-specific load patterns.
  6. `slot_hour` (Integer: 9 to 16): Hour of the scheduled appointment.
  7. `slot_minute` (Integer: 0 or 30): Half-hour slot increment.
  8. `arrival_lead_minutes` (Float):
     $$\text{arrival\_lead\_minutes} = \frac{\text{scheduled\_time} - \text{checked\_in\_time}}{60}$$
     (Positive if patient arrived early; negative if late).
  9. `queue_position_at_checkin` (Integer $\ge 1$): Patient's deterministic position assigned at check-in.
  10. `patients_waiting_ahead` (Integer $\ge 0$): Number of patients currently in queue with status `waiting` ahead of this entry.
  11. `is_doctor_active_consultation` (Binary 0/1): Whether the doctor currently has a patient with status `in_consultation`.
  12. `historical_avg_consultation_minutes` (Float): Doctor/specialty rolling historical consultation duration baseline.

### 2.2 Dataset B: Appointment No-Show Classification (`noshow_dataset`)
- **Unit of Observation**: A booked appointment.
- **Prediction Moment**: At booking confirmation (`POST /api/v1/appointments`) or 24–48 hours prior to the scheduled date.
- **Target Variable**:
  - `is_no_show` (Binary Integer $\in \{0, 1\}$):
    - `1` = No-Show (appointment status `no_show` or patient failed to check in).
    - `0` = Attended (appointment status `checked_in`, `in_progress`, or `completed`).
    - *Exclusion Rule*: Legitimate cancellations (`status == 'cancelled'`) prior to clinic day are excluded from no-show training targets to prevent label contamination.
- **Input Features (Observable strictly at booking time)**:
  1. `lead_time_days` (Integer $\ge 0$): Days between appointment booking timestamp (`created_at.date()`) and `appointment_date`. (Strongest predictive signal in literature: longer lead times correlate with higher no-show probability).
  2. `day_of_week` (Integer: 0=Monday, 6=Sunday): Day of scheduled visit.
  3. `is_weekend` (Binary 0/1): Weekend appointments often show distinct attendance behaviors.
  4. `slot_hour` (Integer: 9 to 16): Early morning vs. mid-day vs. late afternoon.
  5. `doctor_specialty` (Categorical String): Procedural vs. routine specialties.
  6. `consultation_fee` (Float): Out-of-pocket consultation fee in INR.
  7. `patient_prior_appointments` (Integer $\ge 0$): Total historical appointments for this patient prior to this date.
  8. `patient_prior_no_shows` (Integer $\ge 0$): Historical no-shows prior to this date.
  9. `patient_prior_no_show_rate` (Float $[0.0, 1.0]$): Historical ratio $\frac{\text{prior\_no\_shows}}{\text{prior\_appointments}}$ (imputed with population prior for new patients).
  10. `has_notes` (Binary 0/1): Whether patient provided specific visit notes/reasons during booking.

---

## 3. Data Leakage Prevention & Missing-Value Policies

### 3.1 Strict Data Leakage Safeguards
1. **No Future Timestamps**:
   - For wait time: Under no circumstances will `called_at`, `completed_at`, or consultation duration be included in input features.
   - For no-show: Under no circumstances will `checked_in_at`, `queue_entry.id`, token numbers, or doctor action timestamps be included.
2. **Expanding Historical Windows (No Look-Ahead)**:
   - When computing patient historical features (`patient_prior_no_shows`), the calculation must strictly consider appointments where `appointment_date < current_appointment_date`.
3. **No Target Encoding Contamination**:
   - Any categorical encoding (e.g., target encoding or scaling) must be fit exclusively on the training split and applied via scikit-learn `Pipeline` to validation/test splits.

### 3.2 Missing-Value Handling
- `arrival_lead_minutes`: For emergency/walk-in cases where scheduled slot is absent, impute with `0.0` and flag via `is_walkin=1`.
- `patient_prior_no_show_rate`: For first-time patients (`prior_appointments == 0`), impute with the global empirical no-show rate ($\approx 0.18$) using a specialized imputing transformer.
- `consultation_fee`: Impute with specialty median if unlisted.

---

## 4. Evaluation Strategy & Metrics

### 4.1 Chronological Split (Temporal Cross-Validation)
- **Problem with K-Fold**: Random $k$-fold cross-validation leaks future clinic dynamics and seasonal trends into past evaluations.
- **Chronological Split Policy**:
  - Sort dataset strictly by `appointment_date` ascending.
  - **Train Set (First 70%)**: Earliest chronological window.
  - **Validation Set (Next 15%)**: Intermediate chronological window for hyperparameter tuning.
  - **Test Set (Final 15%)**: Most recent chronological holdout window representing unseen future production traffic.
  - Secondary validation: `TimeSeriesSplit(n_splits=5)` for cross-validated stability checks.

### 4.2 Metrics Matrix

#### Waiting-Time Regression Metrics:
- **Primary Metric**: **MAE (Mean Absolute Error)**
  - Clinical rationale: "On average, our wait-time prediction is accurate within $\pm X$ minutes." Highly interpretable for patients and hospital triage staff.
- **Secondary Metric**: **RMSE (Root Mean Squared Error)**
  - Penalizes severe underestimations/overestimations that cause clinic overcrowding.
- **Operational Metric**: **Accuracy Within $\pm 10$ Minutes (%)**
  - Percentage of patients whose actual call time fell within 10 minutes of predicted wait time.
- **Baselines to Beat**:
  1. Naive Mean Wait-Time Regressor.
  2. Fixed Rule-Based Heuristic ($15 \text{ mins} \times \text{position}$).
  3. Candidate Models: Ridge Regression, Random Forest Regressor, XGBoost Regressor.

#### No-Show Classification Metrics:
- **Imbalance Context**: Anticipated no-show prevalence is $15\% - 25\%$. Accuracy is misleading (a naive model predicting all 0s achieves $80\%$ accuracy).
- **Primary Metric**: **PR-AUC (Area Under Precision-Recall Curve)**
  - Evaluates trade-off between precision and recall across all decision thresholds without distortion from true negative volume.
- **Secondary Metrics**:
  - **F1-Score** on positive class (`is_no_show=1`).
  - **Precision & Recall** at calibrated threshold.
  - **ROC-AUC** & Brier Score (probability calibration).
- **Baselines to Beat**:
  1. Dummy Classifier (stratified & most frequent).
  2. Logistic Regression (class-weighted).
  3. Candidate Models: Balanced Random Forest, XGBoost Classifier (`scale_pos_weight`).

---

## 5. Implementation Architecture

### 5.1 Directory Layout
```text
backend/
├── app/
│   ├── ml/
│   │   ├── __init__.py
│   │   ├── config.py              # Registry paths, feature column lists, thresholds
│   │   ├── data_generator.py      # Statistical synthetic generator (clearly labeled)
│   │   ├── preprocessing.py       # Scikit-learn Pipeline transformers, encoders, scalers
│   │   ├── train_wait_time.py     # Chronological train/eval pipeline for regression
│   │   ├── train_noshow.py        # Chronological train/eval pipeline for classification
│   │   ├── service.py             # MLPredictionService runtime with fallback heuristics
│   │   └── artifacts/             # Persistent serialized model pipelines (.joblib) & metrics.json
│   ├── schemas/
│   │   └── ml.py                  # Pydantic request/response schemas for ML endpoints
│   └── api/
│       └── v1/
│           └── predictions.py     # FastAPI endpoints (/wait-time, /no-show, /metrics)
└── tests/
    └── test_ml.py                 # Comprehensive unit & integration tests for ML module
```

### 5.2 Runtime Reliability & Graceful Fallback
- `MLPredictionService` implements the singleton pattern with lazy loading.
- If model artifacts (`.joblib`) are absent or fail checksum validation:
  - Wait-time service falls back safely to deterministic position-based rule:
    $$\text{fallback\_wait} = \max(5, \text{position} \times 15)$$
  - No-show service falls back safely to empirical baseline risk score ($0.18$) with risk tier `low`.
- Ensures zero downtime or 500 errors in clinical queue operations even if ML models are unbuilt or corrupted.

---

## 6. Testing & Verification Matrix

1. **Synthetic Generator Validation**:
   - Verify generated datasets contain strictly zero PII.
   - Verify timestamps obey causality: `created_at` $\le$ `appointment_date` $\le$ `checked_in_at` $\le$ `called_at` $\le$ `completed_at`.
   - Verify distribution sanity (no negative wait times, realistic no-show proportions $15\% - 25\%$).
2. **Feature Engineering Pipeline Tests**:
   - Assert pipeline outputs expected feature shape and column order.
   - Verify imputers handle unknown/unseen categories and null fields without exceptions.
3. **Leakage & Temporal Isolation Tests**:
   - Assert `called_at`, `completed_at`, and final notes are absent from regression feature matrices.
   - Assert train max date $\le$ val min date $\le$ test min date.
4. **Model Performance & Serialization Tests**:
   - Verify candidate models outperform naive baselines.
   - Verify serialized `.joblib` pipelines load cleanly and execute predictions within $< 20 \text{ ms}$.
5. **Fallback Safety Tests**:
   - Verify `MLPredictionService` returns valid fallback estimates when model files are missing.

---

## 7. Plan 6.1 Execution Boundaries
- **No data generated yet.**
- **No models trained yet.**
- **No database changes or migrations.**
- **No changes to `medismart_db`.**
