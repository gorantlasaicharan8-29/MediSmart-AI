from fastapi import APIRouter
from app.api.v1.health import router as health_router
from app.api.v1.auth import router as auth_router
from app.api.v1.hospitals import router as hospitals_router
from app.api.v1.doctors import router as doctors_router
from app.api.v1.appointments import router as appointments_router
from app.api.v1.queue import router as queue_router

api_router = APIRouter()
api_router.include_router(health_router, prefix="", tags=["health"])
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(hospitals_router, prefix="/hospitals", tags=["hospitals"])
api_router.include_router(doctors_router, prefix="/doctors", tags=["doctors"])
api_router.include_router(appointments_router, prefix="/appointments", tags=["appointments"])
api_router.include_router(queue_router, prefix="/queue", tags=["queue"])
