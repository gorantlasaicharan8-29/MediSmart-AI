import os
import sys
from logging.config import fileConfig

from sqlalchemy import create_engine, pool
from alembic import context

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings
from app.models.base import Base
import app.models  # Ensures all 5 models are registered with Base.metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Use sync psycopg2 driver for Alembic migrations.
# Checks for explicit database target via -x db_url=... or DATABASE_URL env var before falling back to settings.
x_args = context.get_x_argument(as_dictionary=True)
target_url = x_args.get("db_url") or os.environ.get("DATABASE_URL") or settings.DATABASE_URL
sync_db_url = target_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")

# Escape % for ConfigParser compatibility
config.set_main_option("sqlalchemy.url", sync_db_url.replace("%", "%%"))


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    context.configure(
        url=sync_db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = create_engine(
        sync_db_url,
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
