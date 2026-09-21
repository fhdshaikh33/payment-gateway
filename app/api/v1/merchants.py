from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_async_db_session
from app.schemas.common import GenericResponse
from app.schemas.merchant import (
    MerchantRegisterRequest,
    MerchantRegisterResponse,
)
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
    result = await MerchantService.register_merchant(session, payload)
    return GenericResponse[MerchantRegisterResponse](
        success=True,
        message="Merchant registered successfully",
        data=result,
    )
