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
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.database import get_async_db, get_db


# --- Database session dependencies ---
def get_db_session() -> Generator[Session, None, None]:
    """Synchronous database session dependency."""
    yield from get_db()


async def get_async_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Asynchronous database session dependency."""
    async for session in get_async_db():
        yield session


# --- Authentication dependencies (JWT-based) ---
async def get_current_user() -> dict[str, Any]:
    """
    JWT authentication dependency stub.

    Decodes JWT access token and returns authenticated user payload.
    """
    return {"sub": "user_id", "roles": ["user"], "disabled": False}


async def get_current_active_user(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Validates that the authenticated user account is active."""
    if current_user.get("disabled", False):
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
        if not any(role in self.allowed_roles for role in user_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User does not have sufficient permissions",
            )
        return current_user
