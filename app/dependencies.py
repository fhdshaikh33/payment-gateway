"""
Dependency injection functions for FastAPI routes.

This module contains:
- Database session dependencies
- Authentication dependencies (JWT-based)
- Role-based access control
"""

from collections.abc import AsyncGenerator, Generator
from typing import Any, Sequence

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, OAuth2PasswordBearer
import jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_async_db, get_db
from app.core.security import decode_jwt


# --- Database session dependencies ---
def get_db_session() -> Generator[Session, None, None]:
    """Synchronous database session dependency."""
    yield from get_db()


async def get_async_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Asynchronous database session dependency."""
    async for session in get_async_db():
        yield session


# --- Authentication dependencies (JWT-based) ---
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.api_v1_prefix}/auth/login",
    auto_error=False,
)
http_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    bearer_credentials: HTTPAuthorizationCredentials | None = Depends(http_bearer),
) -> dict[str, Any]:
    """
    JWT authentication dependency.

    Extracts Bearer token from authorization header, decodes JWT access token,
    and returns the authenticated user payload.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    auth_token = token
    if not auth_token and bearer_credentials:
        auth_token = bearer_credentials.credentials

    if not auth_token:
        raise credentials_exception

    try:
        payload = decode_jwt(auth_token)
        token_type = payload.get("type")
        if token_type and token_type != "access":
            raise credentials_exception

        subject: str | None = payload.get("sub")
        if subject is None:
            raise credentials_exception

        return payload
    except (jwt.PyJWTError, ValueError):
        raise credentials_exception


async def get_current_active_user(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Validates that the authenticated user account is active."""
    if current_user.get("disabled", False) or not current_user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user account",
        )
    return current_user


# --- Role-based access control (RBAC) ---
class RoleChecker:
    """
    Role-based access control dependency.

    Ensures the authenticated user possesses one of the allowed roles.
    """

    def __init__(self, allowed_roles: Sequence[str]) -> None:
        self.allowed_roles = allowed_roles

    def __call__(
        self, current_user: dict[str, Any] = Depends(get_current_user)
    ) -> dict[str, Any]:
        user_roles = current_user.get("roles", [])
        if isinstance(user_roles, str):
            user_roles = [user_roles]
        if not any(role in self.allowed_roles for role in user_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User does not have sufficient permissions",
            )
        return current_user

