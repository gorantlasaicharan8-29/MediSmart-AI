import os
import re
import pytest

from app.core.config import settings

# ---------------------------------------------------------------------------
# Strict Test Database Isolation Guard
# Ensures all pytest executions connect ONLY to medismart_test_db.
# Never connects to, mutates, or deletes from medismart_db.
# ---------------------------------------------------------------------------
raw_url = os.environ.get("DATABASE_URL") or settings.DATABASE_URL
test_db_url = re.sub(r"/medismart_db(\?.*)?$", r"/medismart_test_db\1", raw_url)
if "medismart_test_db" not in test_db_url:
    test_db_url = raw_url.rsplit("/", 1)[0] + "/medismart_test_db"

# Fail-fast assertion: Must contain medismart_test_db
assert "medismart_test_db" in test_db_url, (
    "SECURITY GUARD ACTIVATED: Pytest database URL must target 'medismart_test_db'!"
)

# Apply to environment and settings
os.environ["DATABASE_URL"] = test_db_url
settings.DATABASE_URL = test_db_url

import app.core.database as db_mod
from app.core.database import create_async_engine
from app.main import app
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

# Ensure engine and sessionmaker are strictly bound to isolated test database
if "medismart_test_db" not in str(db_mod.engine.url):
    db_mod.engine = create_async_engine(
        test_db_url,
        echo=False,
        future=True,
        pool_pre_ping=True,
    )
    db_mod.AsyncSessionLocal = async_sessionmaker(
        bind=db_mod.engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )


@pytest.fixture(scope="session", autouse=True)
def fail_safe_db_isolation_check():
    """
    Fail-fast verification guard executed before any test runs.
    Logs sanitized host/database targets without revealing passwords or credentials.
    """
    safe_settings_target = settings.DATABASE_URL.split("@")[-1]
    safe_engine_target = str(db_mod.engine.url).split("@")[-1]

    if "medismart_test_db" not in safe_settings_target:
        raise RuntimeError(
            f"SECURITY GUARD ACTIVATED: settings.DATABASE_URL does not target medismart_test_db! ({safe_settings_target})"
        )
    if "medismart_test_db" not in safe_engine_target:
        raise RuntimeError(
            f"SECURITY GUARD ACTIVATED: active engine does not target medismart_test_db! ({safe_engine_target})"
        )


@pytest.fixture
async def client():
    """Async test client for testing FastAPI endpoints against isolated test DB."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
