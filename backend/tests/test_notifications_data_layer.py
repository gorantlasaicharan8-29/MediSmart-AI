import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal, engine
from app.core.security import get_password_hash
from app.models import Base, Notification, User


def test_notification_model_metadata_registration():
    """Verify Notification model is properly registered with Base metadata."""
    registered_tables = set(Base.metadata.tables.keys())
    assert "notifications" in registered_tables


def test_notification_model_structure():
    """Verify Notification table columns, data types, nullability, and primary key."""
    table = Notification.__table__

    assert "id" in table.columns
    assert isinstance(table.columns["id"].type, UUID)
    assert table.columns["id"].primary_key

    # Foreign key to users
    assert "user_id" in table.columns
    assert isinstance(table.columns["user_id"].type, UUID)
    assert not table.columns["user_id"].nullable
    fk_targets = {fk.target_fullname for fk in table.foreign_keys}
    assert "users.id" in fk_targets

    # Text & Categorization fields
    assert "category" in table.columns
    assert not table.columns["category"].nullable

    assert "event_type" in table.columns
    assert not table.columns["event_type"].nullable

    assert "title" in table.columns
    assert not table.columns["title"].nullable

    assert "message" in table.columns
    assert not table.columns["message"].nullable

    assert "urgency" in table.columns
    assert not table.columns["urgency"].nullable

    # Status & Timestamps
    assert "is_read" in table.columns
    assert not table.columns["is_read"].nullable

    assert "read_at" in table.columns
    assert table.columns["read_at"].nullable

    assert "idempotency_key" in table.columns
    assert table.columns["idempotency_key"].nullable

    assert "metadata_json" in table.columns
    assert isinstance(table.columns["metadata_json"].type, JSONB)
    assert table.columns["metadata_json"].nullable

    assert "created_at" in table.columns
    assert "updated_at" in table.columns


def test_notification_indexes_and_constraints():
    """Verify required indexes and partial unique constraint for idempotency."""
    table = Notification.__table__
    index_names = {idx.name for idx in table.indexes}

    assert "ix_notifications_user_id" in index_names
    assert "ix_notifications_user_read_created" in index_names
    assert "uq_user_notification_idempotency" in index_names

    # Check partial unique index definition
    idempotency_idx = next(idx for idx in table.indexes if idx.name == "uq_user_notification_idempotency")
    assert idempotency_idx.unique
    assert idempotency_idx.dialect_options["postgresql"]["where"] is not None


def test_user_notification_relationship_configuration():
    """Verify User and Notification bidirectional relationship configuration."""
    assert hasattr(User, "notifications")
    assert hasattr(Notification, "user")


@pytest.mark.asyncio
async def test_notification_crud_and_defaults_in_test_db():
    """Verify inserting and querying a Notification with defaults against test DB."""
    async with AsyncSessionLocal() as session:
        # Create a unique test user
        unique_email = f"notif_test_{uuid.uuid4().hex[:8]}@example.com"
        user = User(
            email=unique_email,
            hashed_password=get_password_hash("Secret123!"),
            full_name="Notification Test Patient",
            role="patient",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        # Create a notification with defaults
        notif = Notification(
            user_id=user.id,
            category="appointment",
            event_type="appointment_booked",
            title="Appointment Confirmed",
            message="Your consultation with Dr. Mitchell is confirmed.",
            metadata_json={"appointment_id": str(uuid.uuid4())},
        )
        session.add(notif)
        await session.commit()
        await session.refresh(notif)

        assert notif.id is not None
        assert notif.is_read is False
        assert notif.read_at is None
        assert notif.urgency == "normal"
        assert notif.created_at is not None
        assert notif.metadata_json["appointment_id"] is not None

        # Mark as read
        now = datetime.now(timezone.utc)
        notif.is_read = True
        notif.read_at = now
        await session.commit()
        await session.refresh(notif)

        assert notif.is_read is True
        assert notif.read_at is not None

        # Clean up
        await session.delete(user)
        await session.commit()


@pytest.mark.asyncio
async def test_notification_idempotency_constraint():
    """
    Verify idempotency constraint:
    - Same user + same idempotency_key -> IntegrityError
    - Different user + same idempotency_key -> Success
    - Same user + None idempotency_key -> Success (multiple allowed)
    """
    async with AsyncSessionLocal() as session:
        user1 = User(
            email=f"idemp1_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=get_password_hash("Secret123!"),
            full_name="User 1",
            role="patient",
        )
        user2 = User(
            email=f"idemp2_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=get_password_hash("Secret123!"),
            full_name="User 2",
            role="patient",
        )
        session.add_all([user1, user2])
        await session.commit()
        await session.refresh(user1)
        await session.refresh(user2)

        user1_id = user1.id
        user2_id = user2.id
        shared_key = f"appt_booked_{uuid.uuid4().hex[:8]}"

        # 1. Insert first notification for user 1 with idempotency key
        notif1 = Notification(
            user_id=user1_id,
            category="appointment",
            event_type="appointment_booked",
            title="First",
            message="Message 1",
            idempotency_key=shared_key,
        )
        session.add(notif1)
        await session.commit()

        # 2. Duplicate insertion for same user with same key must fail
        notif1_duplicate = Notification(
            user_id=user1_id,
            category="appointment",
            event_type="appointment_booked",
            title="Duplicate",
            message="Message duplicate",
            idempotency_key=shared_key,
        )
        session.add(notif1_duplicate)
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()

        # 3. Same key for different user (user2) must succeed
        notif2 = Notification(
            user_id=user2_id,
            category="appointment",
            event_type="appointment_booked",
            title="User 2 Notification",
            message="Message user 2",
            idempotency_key=shared_key,
        )
        session.add(notif2)
        await session.commit()

        # 4. Multiple notifications with idempotency_key=None for user 1 must succeed
        null_key_1 = Notification(
            user_id=user1_id,
            category="queue",
            event_type="general",
            title="Null Key 1",
            message="Null Key Msg 1",
            idempotency_key=None,
        )
        null_key_2 = Notification(
            user_id=user1_id,
            category="queue",
            event_type="general",
            title="Null Key 2",
            message="Null Key Msg 2",
            idempotency_key=None,
        )
        session.add_all([null_key_1, null_key_2])
        await session.commit()

        # Clean up
        from sqlalchemy import delete
        await session.execute(delete(User).where(User.id.in_([user1_id, user2_id])))
        await session.commit()


@pytest.mark.asyncio
async def test_user_cascade_deletes_notifications():
    """Verify deleting a User cascades to delete all their notifications."""
    async with AsyncSessionLocal() as session:
        user = User(
            email=f"cascade_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=get_password_hash("Secret123!"),
            full_name="Cascade Test User",
            role="patient",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        notif = Notification(
            user_id=user.id,
            category="system",
            event_type="welcome",
            title="Welcome",
            message="Welcome to MediSmart",
        )
        session.add(notif)
        await session.commit()
        notif_id = notif.id

        # Delete user
        await session.delete(user)
        await session.commit()

        # Notification must be gone
        res = await session.execute(select(Notification).where(Notification.id == notif_id))
        assert res.scalar_one_or_none() is None


def test_notifications_migration_lifecycle_on_test_db():
    """
    Verify additive and reversible Alembic migration on medismart_test_db:
    1. Downgrade from a7c8e91f0d32 to 63b2c1f9d5e2 removes 'notifications' table.
    2. Upgrade to a7c8e91f0d32 recreates 'notifications' table, columns, and indexes.
    Strictly asserts target is medismart_test_db.
    """
    import os
    from pathlib import Path
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, inspect

    test_db_url = os.environ.get("DATABASE_URL", "")
    assert "medismart_test_db" in test_db_url, "Migration test must strictly target medismart_test_db"

    backend_root = Path(r"c:\Users\goran\OneDrive\Desktop\Medi Smart\backend")
    alembic_cfg = Config(str(backend_root / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(backend_root / "alembic"))

    sync_test_url = test_db_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
    engine_sync = create_engine(sync_test_url)

    try:
        # 1. Downgrade to previous revision (63b2c1f9d5e2)
        command.downgrade(alembic_cfg, "63b2c1f9d5e2")
        insp_down = inspect(engine_sync)
        assert "notifications" not in insp_down.get_table_names(), (
            "notifications table must be dropped after downgrade to 63b2c1f9d5e2"
        )

        # 2. Upgrade to new revision (a7c8e91f0d32)
        command.upgrade(alembic_cfg, "a7c8e91f0d32")
        insp_up = inspect(engine_sync)
        assert "notifications" in insp_up.get_table_names(), (
            "notifications table must exist after upgrade to a7c8e91f0d32"
        )

        cols = {c["name"] for c in insp_up.get_columns("notifications")}
        expected_cols = {
            "id", "user_id", "category", "event_type", "title",
            "message", "urgency", "is_read", "read_at", "idempotency_key",
            "metadata_json", "created_at", "updated_at",
        }
        assert expected_cols.issubset(cols)

        idx_names = {i["name"] for i in insp_up.get_indexes("notifications")}
        assert "ix_notifications_user_read_created" in idx_names
        assert "uq_user_notification_idempotency" in idx_names
    finally:
        # Guarantee test database remains at head revision
        command.upgrade(alembic_cfg, "head")

