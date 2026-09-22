import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.merchant import Merchant
from app.models.merchant_member import MerchantMember
from app.models.role import Role
from app.models.user import User


class MerchantRepository:
    """Repository handling database operations for Merchants, Users, Roles, and Members."""

    @staticmethod
    async def get_user_by_email_async(
        session: AsyncSession, email: str
    ) -> Optional[User]:
        """Fetch user by email using async session."""
        result = await session.execute(select(User).where(User.email == email))
        return result.scalars().first()


    @staticmethod
    def get_user_by_email_sync(
        session: Session, email: str
    ) -> Optional[User]:
        """Fetch user by email using sync session."""
        return session.execute(select(User).where(User.email == email)).scalars().first()

    @staticmethod
    async def create_merchant_with_owner_async(
        session: AsyncSession,
        business_name: str,
        legal_entity_type: str,
        full_name: str,
        email: str,
        password_hash: str,
    ) -> tuple[Merchant, User]:
        """Atomically create Merchant, User, default OWNER Role, and MerchantMember."""
        # 1. Create User
        user = User(
            full_name=full_name,
            email=email,
            password_hash=password_hash,
            is_platform_admin=False,
            is_active=True,
        )
        session.add(user)
        await session.flush()

        # 2. Create Merchant
        merchant = Merchant(
            business_name=business_name,
            legal_entity_type=legal_entity_type,
            kyc_status="PENDING",
        )
        session.add(merchant)
        await session.flush()

        # 3. Create default OWNER role for this merchant
        owner_role = Role(
            merchant_id=merchant.id,
            name="OWNER",
            description="Merchant Owner with full privileges",
        )
        session.add(owner_role)
        await session.flush()

        # 4. Create MerchantMember link
        member = MerchantMember(
            merchant_id=merchant.id,
            user_id=user.id,
            role_id=owner_role.id,
            status="ACTIVE",
        )
        session.add(member)
        await session.commit()
        await session.refresh(merchant)
        await session.refresh(user)

        return merchant, user
