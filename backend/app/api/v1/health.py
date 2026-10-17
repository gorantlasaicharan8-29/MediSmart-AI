from fastapi import APIRouter, Response, status
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.core.config import settings

router = APIRouter()


@router.get("/health")
async def health_check():
    """Service health check endpoint."""
    return {"status": "ok", "version": settings.VERSION}


@router.get("/health/db")
async def database_health_check(response: Response):
    """Database connectivity check endpoint."""
    try:
        # Use short timeout for health check so it fails fast if unreachable
        engine = create_async_engine(
            settings.DATABASE_URL,
            connect_args={"timeout": 5},
            pool_pre_ping=True,
        )
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            val = result.scalar()
            await engine.dispose()
            if val == 1:
                return {"status": "ok", "database": "connected"}
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return {"status": "error", "database": "disconnected", "detail": "Unexpected query result"}
    except Exception as exc:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "error", "database": "disconnected", "detail": str(exc)}
