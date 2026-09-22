from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, create_refresh_token, verify_password
from app.models.merchant_member import MerchantMember
from app.models.role import Role
from app.models.user import User
from app.schemas.auth import TokenResponse, LoginRequest


async def authenticate_user(
    session: AsyncSession, request_data: LoginRequest
) -> TokenResponse:
    """Authenticate user and return tokens along with role and status."""
    result = await session.execute(select(User).where(User.email == request_data.email))
    user = result.scalars().first()

    if not user or not verify_password(request_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user account",
        )

    # Get role and status
    stmt = (
        select(Role.name, MerchantMember.status)
        .join(Role, MerchantMember.role_id == Role.id)
        .where(MerchantMember.user_id == user.id)
        .limit(1)
    )
    role_result = await session.execute(stmt)
    row = role_result.first()

    role = row[0] if row else None
    member_status = row[1] if row else None

    access_token = create_access_token(subject=user.id)
    refresh_token = create_refresh_token(subject=user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        role=role,
        status=member_status,
    )
