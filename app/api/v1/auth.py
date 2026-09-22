from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import logger
from app.dependencies import get_async_db_session
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.common import GenericResponse
from app.services.auth_service import authenticate_user

router = APIRouter()


@router.post("/login", response_model=GenericResponse[TokenResponse])
async def login(
    request_data: LoginRequest,
    session: AsyncSession = Depends(get_async_db_session),
):
    """
    Authenticate user and return access token, refresh token, role, and status.
    """
    logger.info("Processing login request for user: %s", request_data.email)
    token_data = await authenticate_user(session, request_data)
    return GenericResponse(
        success=True,
        message="Login successful",
        data=token_data,
    )
