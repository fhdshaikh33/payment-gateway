import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.dependencies import RoleChecker, get_async_db_session, get_current_active_user
from app.models.merchant_member import MerchantMember
from app.schemas.common import GenericResponse
from app.schemas.ledger import LedgerBalanceResponse, LedgerTransactionResponse
from app.services.ledger_service import (
    get_merchant_wallet_balance,
    get_ledger_transaction_by_reference,
)
from sqlalchemy import select

router = APIRouter()
logger = logging.getLogger(__name__)

# Only users with MERCHANT or ACCOUNTANT roles can access this endpoint
allow_merchant_or_accountant = RoleChecker(["MERCHANT", "ACCOUNTANT"])
allow_platform_admin = RoleChecker(["PLATFORM_ADMIN"])


@router.get("/accounts/balance", response_model=GenericResponse[LedgerBalanceResponse])
async def fetch_wallet_balance_endpoint(
    current_user: dict[str, Any] = Depends(allow_merchant_or_accountant),
    db_session: AsyncSession = Depends(get_async_db_session),
) -> GenericResponse[LedgerBalanceResponse]:
    """
    Fetch the real-time cached aggregate balance for the authenticated merchant.
    """
    user_id = uuid.UUID(current_user["sub"])

    # Need to fetch the merchant_id associated with the user
    stmt = select(MerchantMember).where(MerchantMember.user_id == user_id)
    result = await db_session.execute(stmt)
    merchant_member = result.scalars().first()

    if not merchant_member:
        raise HTTPException(
            status_code=403, detail="User is not associated with a merchant"
        )

    merchant_id = merchant_member.merchant_id

    balance_response = await get_merchant_wallet_balance(db_session, merchant_id)

    return GenericResponse(
        success=True,
        message="Wallet balance retrieved successfully",
        data=balance_response,
    )


@router.get(
    "/transactions/{reference_id}",
    response_model=GenericResponse[LedgerTransactionResponse],
)
async def fetch_ledger_transaction_endpoint(
    reference_id: str,
    current_user: dict[str, Any] = Depends(allow_platform_admin),
    db_session: AsyncSession = Depends(get_async_db_session),
) -> GenericResponse[LedgerTransactionResponse]:
    """
    Inspects balanced accounting legs for any payment or refund ID.
    Access: Platform Admin
    """
    transaction_response = await get_ledger_transaction_by_reference(
        db_session, reference_id
    )
    return GenericResponse(
        success=True,
        message="Ledger transaction retrieved successfully",
        data=transaction_response,
    )
