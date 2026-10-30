from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import Settings, settings
from app.api.v1 import api_router
import logging
import app.core.database as db_mod
from app.core.websocket import queue_ws_manager, user_ws_manager

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI):
    """FastAPI application lifecycle managing startup readiness and graceful resource disposal."""
    # Startup: Start WebSocket broadcast backends (InMemory or Redis)
    await queue_ws_manager.start()
    await user_ws_manager.start()

    yield

    # Shutdown: Stop WebSocket broadcast backends and dispose database connection pool
    try:
        await user_ws_manager.stop()
    except Exception as exc:
        logger.warning(f"Error stopping user WebSocket manager during shutdown: {exc}")

    try:
        await queue_ws_manager.stop()
    except Exception as exc:
        logger.warning(f"Error stopping queue WebSocket manager during shutdown: {exc}")

    if hasattr(db_mod, "engine") and db_mod.engine is not None:
        await db_mod.engine.dispose()


def create_app(app_settings: Optional[Settings] = None) -> FastAPI:
    """Application factory configuring routes, CORS, lifespan, and environment-dependent documentation."""
    cfg = app_settings or settings
    docs_url = "/docs" if cfg.DOCS_ENABLED else None
    redoc_url = "/redoc" if cfg.DOCS_ENABLED else None
    openapi_url = "/openapi.json" if cfg.DOCS_ENABLED else None

    application = FastAPI(
        title=cfg.PROJECT_NAME,
        version=cfg.VERSION,
        description="Smart Hospital Discovery, Doctor Appointment & Real-Time Queue Management System",
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
        lifespan=lifespan,
    )

    # CORS Middleware
    application.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount API Routers
    application.include_router(api_router, prefix=cfg.API_V1_PREFIX)

    @application.get("/", tags=["root"])
    async def root():
        return {
            "message": cfg.PROJECT_NAME,
            "docs": docs_url,
            "version": cfg.VERSION,
            "health": f"{cfg.API_V1_PREFIX}/health",
        }

    return application


app = create_app()
