import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import logger
from app.dependencies import get_async_db_session, get_current_active_user
from app.repositories.api_key_repository import ApiKeyRepository
from app.schemas.api_key import (
    ApiKeyGenerateRequest,
    ApiKeyGenerateResponse,
)
from app.schemas.common import GenericResponse
from app.schemas.merchant import (
    MerchantRegisterRequest,
    MerchantRegisterResponse,
)
from app.services.api_key_service import ApiKeyService
from app.services.merchant_service import MerchantService

router = APIRouter()


@router.post(
    "/register",
    response_model=GenericResponse[MerchantRegisterResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Register Merchant & KYC Initial State",
    description="Registers a new merchant entity and primary administrative user.",
)
async def register_merchant(
    payload: MerchantRegisterRequest,
    session: AsyncSession = Depends(get_async_db_session),
) -> GenericResponse[MerchantRegisterResponse]:
    """
    1.1 Merchant Registration & KYC endpoint.

    Creates a new Merchant entity, primary User account, OWNER role,
    and MerchantMember association.
    """
    logger.info(
        "Processing merchant registration for business: %s",
        payload.business_name,
    )
    result = await MerchantService.register_merchant(session, payload)
    return GenericResponse[MerchantRegisterResponse](
        success=True,
        message="Merchant registered successfully",
        data=result,
    )


@router.post(
    "/keys/generate",
    response_model=GenericResponse[ApiKeyGenerateResponse],
    status_code=status.HTTP_200_OK,
    summary="Generate / Rotate API Keys",
    description="Generates or rotates integration keys (key_id and key_secret) for TEST or LIVE environment.",
)
async def generate_api_key(
    payload: ApiKeyGenerateRequest,
    session: AsyncSession = Depends(get_async_db_session),
    current_user: dict = Depends(get_current_active_user),
) -> GenericResponse[ApiKeyGenerateResponse]:
    """
    1.2 Generate / Rotate API Keys endpoint.

    Issues a new key pair for the merchant associated with the authenticated session.
    Automatically deactivates/rotates previous active keys for the specified environment.
    """
    logger.info(
        "Processing API key generation request for environment: %s",
        payload.environment,
    )
    merchant_id = None
    if "merchant_id" in current_user and current_user["merchant_id"]:
        try:
            merchant_id = uuid.UUID(str(current_user["merchant_id"]))
        except ValueError:
            pass

    if not merchant_id and (
        "sub" in current_user or "user_id" in current_user
    ):
        user_id_str = current_user.get("user_id") or current_user.get("sub")
        try:
            user_id = uuid.UUID(str(user_id_str))
            merchant_id = (
                await ApiKeyRepository.get_merchant_id_for_user_async(
                    session, user_id
                )
            )
        except ValueError:
            pass

    if not merchant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No active merchant association found for current user session",
        )

    result = await ApiKeyService.generate_api_key(
        session=session,
        merchant_id=merchant_id,
        environment=payload.environment,
    )

    return GenericResponse[ApiKeyGenerateResponse](
        success=True,
        message="API key generated successfully",
        data=result,
    )
