import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import generate_api_key_pair
from app.repositories.api_key_repository import ApiKeyRepository
from app.schemas.api_key import (
    ApiKeyEnvironment,
    ApiKeyGenerateResponse,
)


class ApiKeyService:
    """Service layer for API key generation and rotation operations."""

    @staticmethod
    async def generate_api_key(
        session: AsyncSession,
        merchant_id: uuid.UUID,
        environment: ApiKeyEnvironment,
    ) -> ApiKeyGenerateResponse:
        """
        Generate a new integration key pair or rotate an existing active key pair
        for the given merchant and environment.
        """
        env_str = environment.value
        key_id, key_secret, key_secret_hash = generate_api_key_pair(env_str)

        api_key = await ApiKeyRepository.create_or_rotate_api_key_async(
            session=session,
            merchant_id=merchant_id,
            environment=env_str,
            key_id=key_id,
            key_secret_hash=key_secret_hash,
        )

        return ApiKeyGenerateResponse(
            key_id=api_key.key_id,
            key_secret=key_secret,
            environment=ApiKeyEnvironment(api_key.environment),
            is_active=api_key.is_active,
            created_at=api_key.created_at,
        )
