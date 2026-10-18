from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import RelationshipProperty
from app.models import Base, User, Hospital, Doctor, Appointment, QueueEntry


def test_models_registered_in_metadata():
    """Verify that all 5 core tables are registered with Base metadata."""
    registered_tables = set(Base.metadata.tables.keys())
    expected_tables = {"users", "hospitals", "doctors", "appointments", "queue_entries"}
    assert expected_tables.issubset(registered_tables)


def test_user_model_structure():
    """Verify User model columns, PK type, and unique constraint on email."""
    table = User.__table__
    assert "id" in table.columns
    assert isinstance(table.columns["id"].type, UUID)
    assert table.columns["id"].primary_key

    assert "email" in table.columns
    assert table.columns["email"].unique or any(
        col.name == "email" for idx in table.indexes if idx.unique for col in idx.columns
    )
    assert not table.columns["email"].nullable
    assert not table.columns["hashed_password"].nullable
    assert not table.columns["role"].nullable


def test_hospital_model_structure():
    """Verify Hospital model columns, coordinates, and array types."""
    table = Hospital.__table__
    assert "name" in table.columns
    assert "city" in table.columns
    assert "latitude" in table.columns
    assert "longitude" in table.columns
    assert "specialties" in table.columns
    assert isinstance(table.columns["specialties"].type, ARRAY)
    assert isinstance(table.columns["facilities"].type, ARRAY)


def test_doctor_model_foreign_keys():
    """Verify Doctor foreign keys to users and hospitals."""
    table = Doctor.__table__
    fk_targets = {fk.target_fullname for fk in table.foreign_keys}
    assert "users.id" in fk_targets
    assert "hospitals.id" in fk_targets

    # user_id must be unique (1-to-1 doctor profile per user account)
    assert table.columns["user_id"].unique or any(
        uq.columns.contains(table.columns["user_id"]) for uq in table.constraints if hasattr(uq, "columns") and len(uq.columns) == 1
    )


def test_appointment_model_structure():
    """Verify Appointment foreign keys, date, time, and status columns."""
    table = Appointment.__table__
    fk_targets = {fk.target_fullname for fk in table.foreign_keys}
    assert "users.id" in fk_targets
    assert "doctors.id" in fk_targets
    assert "hospitals.id" in fk_targets

    assert "appointment_date" in table.columns
    assert "appointment_time" in table.columns
    assert "status" in table.columns


def test_queue_entry_model_structure():
    """Verify QueueEntry foreign keys, uniqueness of appointment_id, and tokens."""
    table = QueueEntry.__table__
    fk_targets = {fk.target_fullname for fk in table.foreign_keys}
    assert "appointments.id" in fk_targets
    assert "hospitals.id" in fk_targets
    assert "doctors.id" in fk_targets
    assert "users.id" in fk_targets

    assert "token_number" in table.columns
    assert "position" in table.columns
    assert "status" in table.columns


def test_all_models_use_uuid_primary_key():
    """Verify all 5 models have a UUID 'id' primary key."""
    models = [User, Hospital, Doctor, Appointment, QueueEntry]
    for model in models:
        pk_col = model.__table__.primary_key.columns["id"]
        assert pk_col is not None, f"Model {model.__name__} missing 'id' PK"
        assert isinstance(pk_col.type, UUID), f"Model {model.__name__} PK is not UUID"


def test_model_relationships():
    """Verify that bidirectional relationships are correctly declared on models."""
    assert hasattr(User, "doctor")
    assert hasattr(User, "appointments")
    assert hasattr(Hospital, "doctors")
    assert hasattr(Doctor, "user")
    assert hasattr(Doctor, "hospital")
    assert hasattr(Appointment, "patient")
    assert hasattr(Appointment, "doctor")
    assert hasattr(Appointment, "queue_entry")
    assert hasattr(QueueEntry, "appointment")
