import asyncio
import logging
import secrets
import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import Payment
from app.models.refund import Refund
from app.schemas.refund import RefundCreateRequest, RefundResponse
from app.services.webhook_service import dispatch_webhook

logger = logging.getLogger(__name__)


async def create_refund(
    db_session: AsyncSession,
    merchant_id: uuid.UUID,
    payment_id: str,
    request_data: RefundCreateRequest,
) -> RefundResponse:
    """
    Process a refund request for a specific payment.
    """
    logger.info(
        f"Initiating refund for payment: {payment_id}, amount: {request_data.amount}"
    )

    # 1. Fetch Payment and ensure it belongs to the merchant
    payment_stmt = select(Payment).where(
        Payment.payment_id == payment_id,
        Payment.merchant_id == merchant_id,
    )
    payment_result = await db_session.execute(payment_stmt)
    payment = payment_result.scalars().first()

    if not payment:
        logger.warning(
            f"Payment {payment_id} not found or doesn't belong to merchant {merchant_id}"
        )
        raise HTTPException(status_code=404, detail="Payment not found")

    # 2. Check if the payment status is eligible for refund (e.g., CAPTURED)
    if payment.status not in ["CAPTURED", "SETTLED"]:
        logger.warning(
            f"Payment {payment_id} is in invalid status for refund: {payment.status}"
        )
        raise HTTPException(
            status_code=400,
            detail="Payment is not in a valid state for refund",
        )

    # 3. Calculate existing refunds to ensure we don't over-refund
    refund_sum_stmt = select(func.sum(Refund.amount)).where(
        Refund.payment_id == payment_id, Refund.status == "PROCESSED"
    )
    refund_sum_result = await db_session.execute(refund_sum_stmt)
    existing_refunds = refund_sum_result.scalar() or 0

    if request_data.amount + existing_refunds > payment.amount:
        logger.warning(
            f"Refund amount {request_data.amount} exceeds remaining refundable amount "
            f"({payment.amount - existing_refunds}) for payment {payment_id}"
        )
        raise HTTPException(
            status_code=400,
            detail="Refund amount exceeds total payment amount",
        )

    # 4. Generate unique refund_id
    refund_id = f"rfn_{secrets.token_hex(6)}"

    # 5. Save the Refund record
    new_refund = Refund(
        refund_id=refund_id,
        payment_id=payment.payment_id,
        merchant_id=payment.merchant_id,
        amount=request_data.amount,
        currency=payment.currency,
        reason=request_data.reason,
        status="PROCESSED",
    )

    try:
        db_session.add(new_refund)
        await db_session.commit()
        await db_session.refresh(new_refund)
        logger.info(
            f"Refund {refund_id} successfully created for payment {payment_id}."
        )

        # 6. Double-Entry Ledger Stub
        # TODO: Insert compensating double-entry debit to Merchant Wallet and credit to Escrow Asset
        logger.info(
            f"Ledger Stub: Debited Merchant Wallet, Credited Escrow Asset for {request_data.amount} {payment.currency}"
        )
        
        # 7. Fire webhook (non-blocking)
        asyncio.create_task(
            dispatch_webhook(
                db_session, 
                merchant_id, 
                "refund.created", 
                {
                    "refund_id": new_refund.refund_id,
                    "payment_id": new_refund.payment_id,
                    "amount": new_refund.amount,
                    "status": new_refund.status,
                }
            )
        )

    except Exception as e:
        await db_session.rollback()
        logger.error(f"Error creating refund record: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while processing refund",
        )

    return RefundResponse(
        refund_id=new_refund.refund_id,
        payment_id=new_refund.payment_id,
        amount=new_refund.amount,
        currency=new_refund.currency,
        status=new_refund.status,
        created_at=new_refund.created_at,
    )
