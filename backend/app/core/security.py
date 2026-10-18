import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Union
import argon2
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
import jwt
from app.core.config import settings

# Argon2id password hasher (RFC 9106 recommended parameters)
_hasher = argon2.PasswordHasher(
    time_cost=2,
    memory_cost=65536,  # 64 MB
    parallelism=1,
    hash_len=32,
    type=argon2.Type.ID,
)


def get_password_hash(password: str) -> str:
    """Hashes a plain text password using Argon2id."""
    return _hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain text password against an Argon2id hash."""
    try:
        return _hasher.verify(hashed_password, plain_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
    except Exception:
        return False


def create_access_token(
    user_id: Union[uuid.UUID, str],
    role: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Creates a securely signed JWT access token with validated claims."""
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload: Dict[str, Any] = {
        "sub": str(user_id),
        "role": str(role),
        "iss": settings.JWT_ISSUER,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "jti": str(uuid.uuid4()),
    }

    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decodes and validates a JWT token signature, expiration, and issuer."""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            issuer=settings.JWT_ISSUER,
            options={
                "require": ["exp", "sub", "role", "iss"],
                "verify_exp": True,
                "verify_iss": True,
            },
        )
        return payload
    except jwt.PyJWTError:
        return None
    except Exception:
        return None
