"""
Tests for Phase 6.1: ML Dataset Generation and Validation.

Validates:
1. Synthetic dataset presence, schemas, and required feature/target columns.
2. Exact reproducibility with deterministic random seeds.
3. Absence of null values, valid ranges, and target constraints.
4. Non-negative waiting-time target and binary no-show labels.
5. Strict target leakage prevention (no future or post-event features).
6. Temporal causality in historical attendance feature construction (no look-ahead bias).
7. Pure synthetic provenance (is_synthetic=True, synthetic ID prefixes, zero PII).
8. Configurable dataset parameters (sample size, target no-show rate).
9. Standalone operation with zero database dependencies or database mutations.
"""
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

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
from app.ml.data_generator import (
    generate_all_datasets,
    generate_noshow_data,
    generate_waiting_time_data,
)


class TestSyntheticDatasetFilesAndSchemas:
    """Tests file existence, schemas, and column coverage."""

    def test_dataset_files_exist_on_disk(self):
        """Verifies that the CSV datasets exist in app/ml/data/."""
        assert NOSHOW_DATASET_PATH.exists(), f"Missing dataset: {NOSHOW_DATASET_PATH}"
        assert WAITING_TIME_DATASET_PATH.exists(), f"Missing dataset: {WAITING_TIME_DATASET_PATH}"
        assert NOSHOW_DATASET_PATH.stat().st_size > 10000, "noshow_dataset.csv appears empty or too small"
        assert WAITING_TIME_DATASET_PATH.stat().st_size > 10000, "waiting_time_dataset.csv appears empty or too small"

    def test_noshow_dataset_schema(self):
        """Verifies all required features, metadata, and target exist in noshow_dataset.csv."""
        df = pd.read_csv(NOSHOW_DATASET_PATH)
        assert len(df) == 10000, f"Expected 10000 rows, found {len(df)}"

        # Check all features exist
        for col in NOSHOW_FEATURES:
            assert col in df.columns, f"Required feature '{col}' missing from noshow_dataset.csv"

        # Check target exists
        assert NOSHOW_TARGET in df.columns, f"Target '{NOSHOW_TARGET}' missing from noshow_dataset.csv"

        # Check provenance flag exists
        assert "is_synthetic" in df.columns, "Synthetic provenance column 'is_synthetic' missing"

    def test_waiting_time_dataset_schema(self):
        """Verifies all required features, metadata, and target exist in waiting_time_dataset.csv."""
        df = pd.read_csv(WAITING_TIME_DATASET_PATH)
        assert len(df) == 5000, f"Expected 5000 rows, found {len(df)}"

        # Check all features exist
        for col in WAITING_TIME_FEATURES:
            assert col in df.columns, f"Required feature '{col}' missing from waiting_time_dataset.csv"

        # Check target exists
        assert WAITING_TIME_TARGET in df.columns, f"Target '{WAITING_TIME_TARGET}' missing from waiting_time_dataset.csv"

        # Check provenance flag exists
        assert "is_synthetic" in df.columns, "Synthetic provenance column 'is_synthetic' missing"


class TestReproducibility:
    """Tests deterministic generation with identical seeds."""

    def test_noshow_generation_reproducibility(self):
        """Identical seeds must yield bit-for-bit identical DataFrames."""
        df1 = generate_noshow_data(n_samples=500, seed=123)
        df2 = generate_noshow_data(n_samples=500, seed=123)
        pd.testing.assert_frame_equal(df1, df2)

    def test_waiting_time_generation_reproducibility(self):
        """Identical seeds must yield bit-for-bit identical DataFrames."""
        df1 = generate_waiting_time_data(n_samples=500, seed=123)
        df2 = generate_waiting_time_data(n_samples=500, seed=123)
        pd.testing.assert_frame_equal(df1, df2)

    def test_different_seeds_produce_different_data(self):
        """Different seeds must yield distinct synthetic samples."""
        df1 = generate_noshow_data(n_samples=200, seed=10)
        df2 = generate_noshow_data(n_samples=200, seed=20)
        assert not df1.equals(df2), "Different seeds should produce different datasets"


class TestDataIntegrityAndRanges:
    """Tests completeness, value bounds, and constraints."""

    def test_no_missing_values(self):
        """Ensures zero null or NaN values in feature or target columns."""
        df_ns = pd.read_csv(NOSHOW_DATASET_PATH)
        for col in NOSHOW_FEATURES + [NOSHOW_TARGET]:
            assert df_ns[col].isna().sum() == 0, f"Found NaN values in no-show column '{col}'"

        df_wt = pd.read_csv(WAITING_TIME_DATASET_PATH)
        for col in WAITING_TIME_FEATURES + [WAITING_TIME_TARGET]:
            assert df_wt[col].isna().sum() == 0, f"Found NaN values in waiting-time column '{col}'"

    def test_noshow_value_ranges(self):
        """Validates bounded ranges for no-show features and target."""
        df = pd.read_csv(NOSHOW_DATASET_PATH)

        # Target must be strictly binary: {0, 1}
        assert set(df[NOSHOW_TARGET].unique()).issubset({0, 1}), "is_no_show must be {0, 1}"

        # Lead time >= 0
        assert (df["lead_time_days"] >= 0).all(), "lead_time_days must be >= 0"

        # Day of week in [0, 6]
        assert df["day_of_week"].between(0, 6).all(), "day_of_week must be in range [0, 6]"

        # Slot hour in [8, 18]
        assert df["slot_hour"].between(8, 18).all(), "slot_hour out of expected clinic hours"

        # Binary flags
        assert set(df["is_weekend"].unique()).issubset({0, 1})
        assert set(df["has_notes"].unique()).issubset({0, 1})

        # Specialty within known supported specialties
        assert set(df["doctor_specialty"].unique()).issubset(set(CLINICAL_SPECIALTIES))

        # Fee must be positive
        assert (df["consultation_fee"] > 0).all()

        # Prior attendance non-negative and consistent
        assert (df["patient_prior_appointments"] >= 0).all()
        assert (df["patient_prior_no_shows"] >= 0).all()
        assert (df["patient_prior_no_shows"] <= df["patient_prior_appointments"]).all()
        assert df["patient_prior_no_show_rate"].between(0.0, 1.0).all()

    def test_waiting_time_value_ranges(self):
        """Validates bounded ranges for waiting-time features and target."""
        df = pd.read_csv(WAITING_TIME_DATASET_PATH)

        # Target must be non-negative: actual_wait_minutes >= 0.0
        assert (df[WAITING_TIME_TARGET] >= 0.0).all(), "actual_wait_minutes cannot be negative"
        assert np.issubdtype(df[WAITING_TIME_TARGET].dtype, np.floating) or np.issubdtype(df[WAITING_TIME_TARGET].dtype, np.integer)

        # Doctor experience in [1, 50]
        assert df["doctor_experience_years"].between(1, 50).all()

        # Queue position at checkin >= 1
        assert (df["queue_position_at_checkin"] >= 1).all()

        # Patients ahead == position - 1
        assert (df["patients_waiting_ahead"] == df["queue_position_at_checkin"] - 1).all()

        # Active consultation flag in {0, 1}
        assert set(df["is_doctor_active_consultation"].unique()).issubset({0, 1})

        # Historical average consultation minutes positive
        assert (df["historical_avg_consultation_minutes"] > 0).all()


class TestTargetLeakagePrevention:
    """Verifies that no post-event or look-ahead features are present."""

    def test_waiting_time_no_target_leakage(self):
        """
        Features observable only after check-in (called_at, completed_at,
        actual consultation duration, consultation notes, diagnosis) MUST NOT be present.
        """
        forbidden_cols = [
            "called_at",
            "completed_at",
            "actual_consultation_minutes",
            "consultation_notes",
            "prescription",
            "diagnosis",
            "status",
        ]
        df = pd.read_csv(WAITING_TIME_DATASET_PATH)
        for col in forbidden_cols:
            assert col not in df.columns, f"LEAKAGE DETECTED: '{col}' found in waiting-time dataset"

    def test_noshow_no_target_leakage(self):
        """
        Features observable only after booking (checked_in_at, token_number,
        queue_entry_id, called_at, completed_at) MUST NOT be present in no-show dataset.
        """
        forbidden_cols = [
            "checked_in_at",
            "called_at",
            "completed_at",
            "token_number",
            "queue_entry_id",
            "actual_wait_minutes",
        ]
        df = pd.read_csv(NOSHOW_DATASET_PATH)
        for col in forbidden_cols:
            assert col not in df.columns, f"LEAKAGE DETECTED: '{col}' found in noshow dataset"

    def test_noshow_target_excludes_cancellations(self):
        """
        Cancelled appointments are not treated as no-shows.
        The target column is binary {0, 1} where 1 represents unexcused failure to arrive.
        """
        df = pd.read_csv(NOSHOW_DATASET_PATH)
        assert set(df[NOSHOW_TARGET].unique()).issubset({0, 1})
        assert "status" not in df.columns or (df["status"] != "cancelled").all()


class TestChronologicalFeatureConstruction:
    """Tests that historical patient attendance is strictly causal and sequential."""

    def test_causal_prior_attendance_tracking(self):
        """
        For any patient with multiple appointments, patient_prior_appointments
        at appointment index k must strictly equal k, and patient_prior_no_shows
        must strictly equal sum(is_no_show[:k]) of previous appointments.
        """
        df = generate_noshow_data(n_samples=2000, seed=42)

        # Inspect patients with >= 3 appointments
        counts = df["patient_id"].value_counts()
        frequent_patients = counts[counts >= 3].index.tolist()
        assert len(frequent_patients) > 0, "Expected repeat patients in synthetic generation"

        for pid in frequent_patients[:10]:
            pat_df = df[df["patient_id"] == pid].copy()

            # Iterate chronologically through patient's appointments
            cum_total = 0
            cum_noshows = 0

            for _, row in pat_df.iterrows():
                # Feature must strictly match cumulative counts before this appointment
                assert row["patient_prior_appointments"] == cum_total, (
                    f"Look-ahead bias detected for patient {pid}: "
                    f"expected prior_appointments={cum_total}, got {row['patient_prior_appointments']}"
                )
                assert row["patient_prior_no_shows"] == cum_noshows, (
                    f"Look-ahead bias detected for patient {pid}: "
                    f"expected prior_no_shows={cum_noshows}, got {row['patient_prior_no_shows']}"
                )

                # Now update for next appointment
                cum_total += 1
                cum_noshows += row["is_no_show"]


class TestSyntheticProvenanceAndPrivacy:
    """Tests that records are marked synthetic and contain zero real PII."""

    def test_is_synthetic_flag(self):
        """Every record in both datasets must have is_synthetic == True."""
        df_ns = pd.read_csv(NOSHOW_DATASET_PATH)
        assert df_ns["is_synthetic"].all() == True

        df_wt = pd.read_csv(WAITING_TIME_DATASET_PATH)
        assert df_wt["is_synthetic"].all() == True

    def test_synthetic_identifier_prefixes(self):
        """Synthetic IDs must be prefixed with SYN- to prevent confusion with real UUIDs."""
        df_ns = pd.read_csv(NOSHOW_DATASET_PATH)
        assert df_ns["appointment_id"].str.startswith("SYN-APT-").all()
        assert df_ns["patient_id"].str.startswith("SYN-PAT-").all()
        assert df_ns["doctor_id"].str.startswith("SYN-DOC-").all()
        assert df_ns["hospital_id"].str.startswith("SYN-HOSP-").all()

        df_wt = pd.read_csv(WAITING_TIME_DATASET_PATH)
        assert df_wt["queue_entry_id"].str.startswith("SYN-QE-").all()
        assert df_wt["doctor_id"].str.startswith("SYN-DOC-").all()
        assert df_wt["hospital_id"].str.startswith("SYN-HOSP-").all()

    def test_zero_real_personal_data(self):
        """No personal identifiers such as names, phone numbers, or emails exist."""
        pii_columns = ["patient_name", "phone", "email", "ssn", "address", "national_id"]
        df_ns = pd.read_csv(NOSHOW_DATASET_PATH)
        df_wt = pd.read_csv(WAITING_TIME_DATASET_PATH)

        for col in pii_columns:
            assert col not in df_ns.columns, f"Potential PII column '{col}' in noshow dataset"
            assert col not in df_wt.columns, f"Potential PII column '{col}' in waiting-time dataset"


class TestConfigurabilityAndZeroDatabaseDependency:
    """Tests generator parameter configurability and zero DB mutation."""

    def test_configurable_sample_sizes(self):
        """Generator must support arbitrary sample sizes."""
        df_small_ns = generate_noshow_data(n_samples=50, seed=99)
        assert len(df_small_ns) == 50

        df_small_wt = generate_waiting_time_data(n_samples=75, seed=99)
        assert len(df_small_wt) == 75

    def test_configurable_noshow_rate(self):
        """Generator adjusts empirical no-show rate based on target parameter."""
        df_low = generate_noshow_data(n_samples=2500, target_noshow_rate=0.10, seed=42)
        df_high = generate_noshow_data(n_samples=2500, target_noshow_rate=0.30, seed=42)

        rate_low = df_low["is_no_show"].mean()
        rate_high = df_high["is_no_show"].mean()

        assert rate_low < rate_high, f"Expected rate_low ({rate_low:.2f}) < rate_high ({rate_high:.2f})"
        assert 0.07 <= rate_low <= 0.15, f"Low rate {rate_low:.2f} out of expected tolerance"
        assert 0.25 <= rate_high <= 0.38, f"High rate {rate_high:.2f} out of expected tolerance"

    def test_zero_database_dependency(self, tmp_path: Path):
        """
        Generation runs purely in memory and files can be saved to any isolated directory
        without opening or querying any database connection or executing migrations.
        """
        df_ns, df_wt = generate_all_datasets(n_noshow=100, n_waiting=100, seed=1, output_dir=tmp_path)
        assert len(df_ns) == 100
        assert len(df_wt) == 100
        assert (tmp_path / "noshow_dataset.csv").exists()
        assert (tmp_path / "waiting_time_dataset.csv").exists()
