import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import RoleChecker, get_async_db_session
from app.schemas.admin import (
    AuditLogResponse,
    MerchantAdminDetail,
    MerchantAdminSummary,
    SystemHealthResponse,
    UpdateKycReviewRequest,
    UpdateMerchantStatusRequest,
)
from app.schemas.common import GenericResponse, PaginatedResponse
from app.services.admin_service import AdminService

router = APIRouter()

# RBAC checkers
allow_platform_admin = RoleChecker(["PLATFORM_ADMIN"])
allow_admin_or_ops = RoleChecker(["PLATFORM_ADMIN", "OPS_AGENT", "RISK_ANALYST"])


@router.get(
    "/merchants",
    response_model=GenericResponse[PaginatedResponse[MerchantAdminSummary]],
    summary="List Merchants (Admin)",
    description="Lists all merchants with filtering by KYC status or search query. Requires Admin/Ops permissions.",
)
async def list_merchants_endpoint(
    kyc_status: Optional[str] = Query(
        None, description="Filter by KYC status (PENDING, APPROVED, REJECTED)"
    ),
    search: Optional[str] = Query(None, description="Search business name"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict[str, Any] = Depends(allow_admin_or_ops),
    session: AsyncSession = Depends(get_async_db_session),
) -> GenericResponse[PaginatedResponse[MerchantAdminSummary]]:
    """List merchants with pagination and filters."""
    summaries, total = await AdminService.list_merchants(
        session=session,
        kyc_status=kyc_status,
        search=search,
        limit=limit,
        offset=offset,
    )
    return GenericResponse(
        success=True,
        message="Merchants retrieved successfully",
        data=PaginatedResponse(
            total=total,
            limit=limit,
            offset=offset,
            data=summaries,
        ),
    )


@router.get(
    "/merchants/{merchant_id}",
    response_model=GenericResponse[MerchantAdminDetail],
    summary="Get Merchant Details (Admin)",
    description="Retrieves complete merchant profile, associated users, and active API keys.",
)
async def get_merchant_detail_endpoint(
    merchant_id: uuid.UUID,
    current_user: dict[str, Any] = Depends(allow_admin_or_ops),
    session: AsyncSession = Depends(get_async_db_session),
) -> GenericResponse[MerchantAdminDetail]:
    """Get comprehensive merchant detail."""
    detail = await AdminService.get_merchant_detail(session, merchant_id)
    return GenericResponse(
        success=True,
        message="Merchant detail retrieved successfully",
        data=detail,
    )


@router.patch(
    "/merchants/{merchant_id}/status",
    response_model=GenericResponse[MerchantAdminDetail],
    summary="Update Merchant Status (Admin)",
    description="Updates merchant operational status (APPROVED, SUSPENDED, REJECTED) and records audit trail.",
)
async def update_merchant_status_endpoint(
    merchant_id: uuid.UUID,
    payload: UpdateMerchantStatusRequest,
    current_user: dict[str, Any] = Depends(allow_platform_admin),
    session: AsyncSession = Depends(get_async_db_session),
) -> GenericResponse[MerchantAdminDetail]:
    """Update merchant account status."""
    admin_user_id = uuid.UUID(current_user["sub"]) if "sub" in current_user else None
    admin_user_email = current_user.get("email")

    detail = await AdminService.update_merchant_status(
        session=session,
        merchant_id=merchant_id,
        new_status=payload.status.value,
        reason=payload.reason,
        admin_user_id=admin_user_id,
        admin_user_email=admin_user_email,
    )
    return GenericResponse(
        success=True,
        message=f"Merchant status updated to {payload.status.value}",
        data=detail,
    )


@router.post(
    "/merchants/{merchant_id}/kyc",
    response_model=GenericResponse[MerchantAdminDetail],
    summary="Submit Merchant KYC Evaluation",
    description="Evaluates merchant KYC compliance document review and records auditor notes.",
)
async def update_merchant_kyc_endpoint(
    merchant_id: uuid.UUID,
    payload: UpdateKycReviewRequest,
    current_user: dict[str, Any] = Depends(allow_admin_or_ops),
    session: AsyncSession = Depends(get_async_db_session),
) -> GenericResponse[MerchantAdminDetail]:
    """Submit KYC compliance review decision."""
    admin_user_id = uuid.UUID(current_user["sub"]) if "sub" in current_user else None
    admin_user_email = current_user.get("email")

    detail = await AdminService.update_merchant_kyc(
        session=session,
        merchant_id=merchant_id,
        kyc_status=payload.kyc_status.value,
        notes=payload.notes,
        admin_user_id=admin_user_id,
        admin_user_email=admin_user_email,
    )
    return GenericResponse(
        success=True,
        message="Merchant KYC evaluation recorded successfully",
        data=detail,
    )


@router.get(
    "/system/health",
    response_model=GenericResponse[SystemHealthResponse],
    summary="System Health & Operations Status",
    description="Performs operational health checks across Database connection pool, Redis cache, and subsystem latencies.",
)
async def system_health_endpoint(
    current_user: dict[str, Any] = Depends(allow_admin_or_ops),
    session: AsyncSession = Depends(get_async_db_session),
) -> GenericResponse[SystemHealthResponse]:
    """Retrieve system health and service status."""
    health_data = await AdminService.check_system_health(session)
    return GenericResponse(
        success=True,
        message="System health check executed successfully",
        data=health_data,
    )


@router.get(
    "/audit-logs",
    response_model=GenericResponse[PaginatedResponse[AuditLogResponse]],
    summary="List Admin Audit Trail Logs",
    description="Retrieves operational audit log history recorded for admin administrative actions.",
)
async def list_audit_logs_endpoint(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict[str, Any] = Depends(allow_platform_admin),
    session: AsyncSession = Depends(get_async_db_session),
) -> GenericResponse[PaginatedResponse[AuditLogResponse]]:
    """List operational admin audit log records."""
    logs, total = await AdminService.list_audit_logs(
        session=session, limit=limit, offset=offset
    )
    return GenericResponse(
        success=True,
        message="Audit logs retrieved successfully",
        data=PaginatedResponse(
            total=total,
            limit=limit,
            offset=offset,
            data=logs,
        ),
    )
