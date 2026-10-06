import logging
import time
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.redis import redis_client
from app.models.api_key import ApiKey
from app.models.audit_log import AdminAuditLog
from app.models.merchant import Merchant
from app.models.merchant_member import MerchantMember
from app.models.payment import Payment
from app.models.role import Role
from app.models.user import User
from app.schemas.admin import (
    ApiKeySummary,
    AuditLogResponse,
    ComponentHealth,
    MerchantAdminDetail,
    MerchantAdminSummary,
    MerchantMemberSummary,
    SystemHealthResponse,
)

logger = logging.getLogger(__name__)


async def record_audit_log(
    session: AsyncSession,
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    user_id: Optional[uuid.UUID] = None,
    user_email: Optional[str] = None,
    details: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> AdminAuditLog:
    """Record an entry in the admin audit log."""
    log_entry = AdminAuditLog(
        user_id=user_id,
        user_email=user_email,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=ip_address,
    )
    session.add(log_entry)
    await session.commit()
    await session.refresh(log_entry)
    return log_entry


class AdminService:
    """Service layer for Platform Admin & Operations tasks."""

    @staticmethod
    async def list_merchants(
        session: AsyncSession,
        kyc_status: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[List[MerchantAdminSummary], int]:
        """
        Query merchants with filtering, pagination, and aggregate stats.
        """
        stmt = select(Merchant)
        count_stmt = select(func.count(Merchant.id))

        if kyc_status:
            stmt = stmt.where(Merchant.kyc_status == kyc_status)
            count_stmt = count_stmt.where(Merchant.kyc_status == kyc_status)

        if search:
            search_pattern = f"%{search}%"
            stmt = stmt.where(Merchant.business_name.ilike(search_pattern))
            count_stmt = count_stmt.where(Merchant.business_name.ilike(search_pattern))

        stmt = stmt.order_by(Merchant.created_at.desc()).limit(limit).offset(offset)

        total_res = await session.execute(count_stmt)
        total = total_res.scalar() or 0

        res = await session.execute(stmt)
        merchants = res.scalars().all()

        summaries = []
        for m in merchants:
            # Query active API keys count
            key_cnt_stmt = select(func.count(ApiKey.id)).where(
                ApiKey.merchant_id == m.id,
                ApiKey.is_active == True,
            )
            key_res = await session.execute(key_cnt_stmt)
            active_keys_count = key_res.scalar() or 0

            # Query total payments count
            pmt_cnt_stmt = select(func.count(Payment.id)).where(
                Payment.merchant_id == m.id
            )
            pmt_res = await session.execute(pmt_cnt_stmt)
            total_payments_count = pmt_res.scalar() or 0

            summaries.append(
                MerchantAdminSummary(
                    merchant_id=m.id,
                    business_name=m.business_name,
                    legal_entity_type=m.legal_entity_type,
                    kyc_status=m.kyc_status,
                    created_at=m.created_at,
                    active_keys_count=active_keys_count,
                    total_payments_count=total_payments_count,
                )
            )

        return summaries, total

    @staticmethod
    async def get_merchant_detail(
        session: AsyncSession, merchant_id: uuid.UUID
    ) -> MerchantAdminDetail:
        """Fetch comprehensive merchant detail including team members and API keys."""
        stmt = select(Merchant).where(Merchant.id == merchant_id)
        res = await session.execute(stmt)
        merchant = res.scalar_one_or_none()

        if not merchant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Merchant with ID {merchant_id} not found",
            )

        # Query merchant members
        members_stmt = (
            select(MerchantMember, User, Role)
            .join(User, MerchantMember.user_id == User.id)
            .outerjoin(Role, MerchantMember.role_id == Role.id)
            .where(MerchantMember.merchant_id == merchant_id)
        )
        members_res = await session.execute(members_stmt)
        member_rows = members_res.all()

        member_summaries = []
        for mm, user_obj, role_obj in member_rows:
            member_summaries.append(
                MerchantMemberSummary(
                    user_id=user_obj.id,
                    full_name=user_obj.full_name,
                    email=user_obj.email,
                    role_name=role_obj.name if role_obj else "MEMBER",
                )
            )

        # Query API keys
        keys_stmt = select(ApiKey).where(ApiKey.merchant_id == merchant_id)
        keys_res = await session.execute(keys_stmt)
        keys_db = keys_res.scalars().all()

        key_summaries = [
            ApiKeySummary(
                key_id=k.key_id,
                environment=k.environment,
                is_active=k.is_active,
                created_at=k.created_at,
            )
            for k in keys_db
        ]

        return MerchantAdminDetail(
            merchant_id=merchant.id,
            business_name=merchant.business_name,
            legal_entity_type=merchant.legal_entity_type,
            kyc_status=merchant.kyc_status,
            created_at=merchant.created_at,
            members=member_summaries,
            api_keys=key_summaries,
        )

    @staticmethod
    async def update_merchant_status(
        session: AsyncSession,
        merchant_id: uuid.UUID,
        new_status: str,
        reason: Optional[str],
        admin_user_id: Optional[uuid.UUID] = None,
        admin_user_email: Optional[str] = None,
    ) -> MerchantAdminDetail:
        """Update merchant account status and record audit log entry."""
        stmt = select(Merchant).where(Merchant.id == merchant_id)
        res = await session.execute(stmt)
        merchant = res.scalar_one_or_none()

        if not merchant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Merchant with ID {merchant_id} not found",
            )

        old_status = merchant.kyc_status
        merchant.kyc_status = new_status
        await session.commit()

        await record_audit_log(
            session=session,
            user_id=admin_user_id,
            user_email=admin_user_email,
            action="MERCHANT_STATUS_UPDATE",
            resource_type="merchant",
            resource_id=str(merchant_id),
            details=f"Status changed from {old_status} to {new_status}. Reason: {reason or 'N/A'}",
        )

        return await AdminService.get_merchant_detail(session, merchant_id)

    @staticmethod
    async def update_merchant_kyc(
        session: AsyncSession,
        merchant_id: uuid.UUID,
        kyc_status: str,
        notes: Optional[str],
        admin_user_id: Optional[uuid.UUID] = None,
        admin_user_email: Optional[str] = None,
    ) -> MerchantAdminDetail:
        """Review merchant KYC compliance and update notes."""
        return await AdminService.update_merchant_status(
            session=session,
            merchant_id=merchant_id,
            new_status=kyc_status,
            reason=f"KYC Review: {notes or 'No notes provided'}",
            admin_user_id=admin_user_id,
            admin_user_email=admin_user_email,
        )

    @staticmethod
    async def check_system_health(session: AsyncSession) -> SystemHealthResponse:
        """Perform active health checks for database and redis dependencies."""
        components = []
        overall_healthy = True

        # DB Check
        t0 = time.time()
        try:
            await session.execute(select(1))
            latency = (time.time() - t0) * 1000
            components.append(
                ComponentHealth(
                    name="PostgreSQL",
                    status="HEALTHY",
                    latency_ms=round(latency, 2),
                    message="Database connected and responsive",
                )
            )
        except Exception as e:
            overall_healthy = False
            components.append(
                ComponentHealth(
                    name="PostgreSQL",
                    status="UNHEALTHY",
                    latency_ms=None,
                    message=f"Database check failed: {str(e)}",
                )
            )

        # Redis Check
        t0 = time.time()
        try:
            pong = await redis_client.ping()
            latency = (time.time() - t0) * 1000
            if pong:
                components.append(
                    ComponentHealth(
                        name="Redis",
                        status="HEALTHY",
                        latency_ms=round(latency, 2),
                        message="Redis PONG received",
                    )
                )
            else:
                overall_healthy = False
                components.append(
                    ComponentHealth(
                        name="Redis",
                        status="UNHEALTHY",
                        latency_ms=None,
                        message="Redis PING returned False",
                    )
                )
        except Exception as e:
            components.append(
                ComponentHealth(
                    name="Redis",
                    status="DEGRADED",
                    latency_ms=None,
                    message=f"Redis connection warning: {str(e)}",
                )
            )

        return SystemHealthResponse(
            status="HEALTHY" if overall_healthy else "DEGRADED",
            timestamp=datetime.now(timezone.utc),
            components=components,
        )

    @staticmethod
    async def list_audit_logs(
        session: AsyncSession, limit: int = 50, offset: int = 0
    ) -> Tuple[List[AuditLogResponse], int]:
        """Fetch audit log history."""
        stmt = (
            select(AdminAuditLog)
            .order_by(AdminAuditLog.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        count_stmt = select(func.count(AdminAuditLog.id))

        total_res = await session.execute(count_stmt)
        total = total_res.scalar() or 0

        res = await session.execute(stmt)
        logs = res.scalars().all()

        log_responses = [AuditLogResponse.model_validate(log) for log in logs]
        return log_responses, total
