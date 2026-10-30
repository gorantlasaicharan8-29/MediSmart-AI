from app.schemas.auth import (
    UserRegisterRequest,
    UserLoginRequest,
    UserResponse,
    TokenResponse,
)
from app.schemas.hospital import (
    HospitalBase,
    HospitalCreate,
    HospitalUpdate,
    HospitalResponse,
    HospitalListResponse,
)

from app.schemas.doctor import (
    DoctorBase,
    DoctorCreate,
    DoctorUpdate,
    DoctorResponse,
    DoctorListResponse,
    DoctorSlot,
    DoctorSlotsDayResponse,
    DoctorProfileSelfUpdate,
    DoctorNextAppointmentSummary,
    DoctorDashboardStatsResponse,
)
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentCancelRequest,
    AppointmentResponse,
    AppointmentListResponse,
)
from app.schemas.queue import (
    QueueCheckInRequest,
    QueueActionRequest,
    QueuePublicItem,
    QueuePublicBoardResponse,
    QueueEntryResponse,
    DoctorQueueItemResponse,
    DoctorQueueResponse,
)

from app.schemas.ml import (
    WaitingTimePredictionRequest,
    WaitingTimePredictionResponse,
    NoShowPredictionRequest,
    NoShowPredictionResponse,
)
from app.schemas.notification import (
    NotificationResponse,
    NotificationListResponse,
    NotificationReadAllResponse,
)

__all__ = [
    "UserRegisterRequest",
    "UserLoginRequest",
    "UserResponse",
    "TokenResponse",
    "HospitalBase",
    "HospitalCreate",
    "HospitalUpdate",
    "HospitalResponse",
    "HospitalListResponse",
    "DoctorBase",
    "DoctorCreate",
    "DoctorUpdate",
    "DoctorResponse",
    "DoctorListResponse",
    "DoctorSlot",
    "DoctorSlotsDayResponse",
    "AppointmentCreate",
    "AppointmentCancelRequest",
    "AppointmentResponse",
    "AppointmentListResponse",
    "QueueCheckInRequest",
    "QueueActionRequest",
    "QueuePublicItem",
    "QueuePublicBoardResponse",
    "QueueEntryResponse",
    "DoctorQueueItemResponse",
    "DoctorQueueResponse",
    "WaitingTimePredictionRequest",
    "WaitingTimePredictionResponse",
    "NoShowPredictionRequest",
    "NoShowPredictionResponse",
    "NotificationResponse",
    "NotificationListResponse",
    "NotificationReadAllResponse",
]
