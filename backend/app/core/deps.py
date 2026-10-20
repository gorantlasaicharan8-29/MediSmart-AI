from typing import Callable, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User


def get_token_from_request(request: Request) -> Optional[str]:
    """
    Extract JWT token from request.
    Dual transport:
    1. First checks HttpOnly cookie 'access_token'.
    2. Fallback to 'Authorization: Bearer <token>' header.
    """
    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        return cookie_token

    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header.split(" ", 1)[1].strip()

    return None


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Validate the token from cookie or header and retrieve the authenticated user from the database.
    Raises 401 Unauthorized for missing, expired, or invalid credentials.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = get_token_from_request(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(token)
    if not payload:
        raise credentials_exception

    # Enforce issuer validation
    if payload.get("iss") != settings.JWT_ISSUER:
        raise credentials_exception

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise credentials_exception

    try:
        user_uuid = UUID(user_id_str)
    except (ValueError, TypeError):
        raise credentials_exception

    query = select(User).where(User.id == user_uuid)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    # Authoritative database-backed hospital affiliation:
    # 1. Never trust X-Hospital-Id or other client-controlled headers.
    # 2. Do not grant access solely because a JWT contains a hospital_id claim.
    # 3. The user's active affiliation is strictly sourced from user.hospital_id in the database.
    # 4. If the affiliation is revoked or altered in the database, subsequent requests
    #    immediately reflect the database state and fail closed.
    # 5. If a JWT token claims a hospital_id that contradicts the active database affiliation,
    #    reject with 401 Unauthorized immediately.
    hosp_claim = payload.get("hospital_id")
    if user.role == "hospital_admin":
        if hosp_claim and user.hospital_id and str(hosp_claim) != str(user.hospital_id):
            raise credentials_exception

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Verify that the authenticated user's account is active.
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account",
        )
    return current_user


def require_roles(*allowed_roles: str) -> Callable:
    """
    Dependency factory to enforce backend Role-Based Access Control (RBAC).
    Checks if the authenticated active user possesses one of the allowed roles.
    Raises 403 Forbidden if the user's role is not authorized.
    """
    async def role_checker(
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: insufficient role permissions",
            )
        return current_user

    return role_checker
