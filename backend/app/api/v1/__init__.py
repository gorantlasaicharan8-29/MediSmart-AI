from fastapi import APIRouter
from app.api.v1.health import router as health_router
from app.api.v1.auth import router as auth_router
from app.api.v1.hospitals import router as hospitals_router
from app.api.v1.doctors import router as doctors_router
from app.api.v1.appointments import router as appointments_router
from app.api.v1.queue import router as queue_router
from app.api.v1.predictions import router as predictions_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.recommendations import router as recommendations_router
from app.api.v1.ehr import router as ehr_router
from app.api.v1.cdss import router as cdss_router
from app.api.v1.medical_reports import router as medical_reports_router

api_router = APIRouter()
api_router.include_router(health_router, prefix="", tags=["health"])
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(hospitals_router, prefix="/hospitals", tags=["hospitals"])
api_router.include_router(doctors_router, prefix="/doctors", tags=["doctors"])
api_router.include_router(appointments_router, prefix="/appointments", tags=["appointments"])
api_router.include_router(queue_router, prefix="/queue", tags=["queue"])
api_router.include_router(predictions_router, prefix="/predictions", tags=["predictions"])
api_router.include_router(notifications_router, prefix="/notifications", tags=["notifications"])
api_router.include_router(recommendations_router, prefix="/recommendations", tags=["recommendations"])
api_router.include_router(ehr_router, prefix="/ehr", tags=["ehr"])
api_router.include_router(cdss_router, prefix="/cdss", tags=["cdss"])
api_router.include_router(medical_reports_router, prefix="/medical-reports", tags=["medical-reports"])
