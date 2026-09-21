from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.repositories.merchant_repository import MerchantRepository
from app.schemas.merchant import (
    MerchantRegisterRequest,
    MerchantRegisterResponse,
)


class MerchantService:
    """Service layer for merchant operations."""

    @staticmethod
    async def register_merchant(
        session: AsyncSession, request: MerchantRegisterRequest
    ) -> MerchantRegisterResponse:
        """
        Register a new merchant account along with its primary owner user.

        Raises HTTP 400 if user email is already registered.
        """
        existing_user = await MerchantRepository.get_user_by_email_async(
            session, request.email
        )
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email address is already registered",
            )

        pwd_hash = hash_password(request.password)

        merchant, user = await MerchantRepository.create_merchant_with_owner_async(
            session=session,
            business_name=request.business_name,
            legal_entity_type=request.legal_entity_type.value,
            full_name=request.full_name,
            email=request.email,
            password_hash=pwd_hash,
        )

        return MerchantRegisterResponse(
            merchant_id=merchant.id,
            business_name=merchant.business_name,
            legal_entity_type=merchant.legal_entity_type,
            kyc_status=merchant.kyc_status,
            user_id=user.id,
            full_name=user.full_name,
            email=user.email,
            created_at=merchant.created_at,
        )
