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
)
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentCancelRequest,
    AppointmentResponse,
    AppointmentListResponse,
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
]
