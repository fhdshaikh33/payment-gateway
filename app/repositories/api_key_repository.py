import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_key import ApiKey
from app.models.merchant_member import MerchantMember


class ApiKeyRepository:
    """Repository handling database operations for Merchant API Integration Keys."""

    @staticmethod
    async def get_merchant_id_for_user_async(
        session: AsyncSession, user_id: uuid.UUID
    ) -> Optional[uuid.UUID]:
        """Fetch merchant_id associated with an active user member."""
        stmt = select(MerchantMember.merchant_id).where(
            MerchantMember.user_id == user_id,
            MerchantMember.status == "ACTIVE",
        )
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def create_or_rotate_api_key_async(
        session: AsyncSession,
        merchant_id: uuid.UUID,
        environment: str,
        key_id: str,
        key_secret_hash: str,
    ) -> ApiKey:
        """
        Deactivates existing active API keys for the specified environment and merchant,
        then creates and returns the new active ApiKey instance.
        """
        now = datetime.now(timezone.utc)

        # Deactivate any existing active keys for this merchant and environment
        deactivate_stmt = (
            update(ApiKey)
            .where(
                ApiKey.merchant_id == merchant_id,
                ApiKey.environment == environment,
                ApiKey.is_active.is_(True),
            )
            .values(is_active=False, revoked_at=now)
        )
        await session.execute(deactivate_stmt)

        # Create new API Key record
        api_key = ApiKey(
            merchant_id=merchant_id,
            key_id=key_id,
            key_secret_hash=key_secret_hash,
            environment=environment,
            is_active=True,
        )
        session.add(api_key)
        await session.commit()
        await session.refresh(api_key)

        return api_key
