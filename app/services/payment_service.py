import hashlib
import hmac
import logging
import secrets
import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decrypt_api_secret
from app.models.api_key import ApiKey
from app.models.order import Order
from app.models.payment import Payment
from app.repositories.api_key_repository import ApiKeyRepository
from app.schemas.payment import (
    ProcessPaymentRequest,
    ProcessPaymentResponse,
    VerifyPaymentRequest,
    VerifyPaymentResponse,
)
from app.services.order_service import get_order_by_public_id

logger = logging.getLogger(__name__)


async def process_payment(
    db_session: AsyncSession, request_data: ProcessPaymentRequest
) -> ProcessPaymentResponse:
    """Process a payment from the checkout modal."""
    logger.info(f"Processing payment for order: {request_data.order_id}")

    # 1. Validate API Key
    api_key = await ApiKeyRepository.get_by_key_id_async(
        db_session, request_data.key_id
    )
    if not api_key:
        logger.warning(f"Invalid API Key provided: {request_data.key_id}")
        raise HTTPException(status_code=401, detail="Invalid API Key")

    # 2. Validate Order
    order = await get_order_by_public_id(
        db_session, request_data.order_id, api_key.merchant_id
    )
    if not order:
        logger.warning(
            f"Order {request_data.order_id} not found or doesn't belong to merchant {api_key.merchant_id}"
        )
        raise HTTPException(status_code=404, detail="Order not found")

    if order.status != "CREATED":
        logger.warning(
            f"Order {request_data.order_id} is in invalid status: {order.status}"
        )
        raise HTTPException(
            status_code=400, detail="Order is not in a valid state for payment"
        )

    # 3. Mock Payment Gateway Logic (e.g. 3DS Challenge)
    payment_id = f"pay_{secrets.token_hex(7)}"
    status = "PENDING"
    action = "3DS_CHALLENGE"
    challenge_url = (
        f"https://api.yourgateway.com/v1/switch/mock-3ds/{payment_id}"
    )

    # 4. Save Payment Record
    new_payment = Payment(
        payment_id=payment_id,
        order_id=order.order_id,
        merchant_id=api_key.merchant_id,
        amount=order.amount,
        currency=order.currency,
        status=status,
        method=request_data.method,
        action=action,
        challenge_url=challenge_url,
    )

    try:
        db_session.add(new_payment)
        await db_session.commit()
        await db_session.refresh(new_payment)
        logger.info(
            f"Payment {payment_id} successfully created and pending 3DS."
        )
    except Exception as e:
        await db_session.rollback()
        logger.error(f"Error creating payment record: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while processing payment",
        )

    return ProcessPaymentResponse(
        payment_id=payment_id,
        order_id=order.order_id,
        status=status,
        action=action,
        challenge_url=challenge_url,
    )


async def verify_payment_signature(
    db_session: AsyncSession,
    request_data: VerifyPaymentRequest,
    merchant_id: uuid.UUID,
    raw_api_secret: str,
) -> VerifyPaymentResponse:
    """
    Verify that a payment signature is authentic.

    The expected signature is HMAC-SHA256 of '<order_id>|<payment_id>'
    keyed with the merchant's plaintext API secret. Uses constant-time
    comparison to prevent timing attacks.

    On successful verification:
      - payment.status is updated to 'CAPTURED'
      - order.status is updated to 'PAID'
    """
    logger.info(
        f"Verifying signature for payment={request_data.payment_id} "
        f"order={request_data.order_id} merchant={merchant_id}"
    )

    # 1. Fetch Payment — scoped to this merchant
    payment_stmt = select(Payment).where(
        Payment.payment_id == request_data.payment_id,
        Payment.merchant_id == merchant_id,
    )
    payment_result = await db_session.execute(payment_stmt)
    payment = payment_result.scalars().first()

    if not payment:
        logger.warning(
            f"Payment {request_data.payment_id} not found for merchant {merchant_id}"
        )
        raise HTTPException(
            status_code=404,
            detail="Payment not found",
        )

    # 2. Fetch Order — scoped to this merchant
    order_stmt = select(Order).where(
        Order.order_id == request_data.order_id,
        Order.merchant_id == merchant_id,
    )
    order_result = await db_session.execute(order_stmt)
    order = order_result.scalars().first()

    if not order:
        logger.warning(
            f"Order {request_data.order_id} not found for merchant {merchant_id}"
        )
        raise HTTPException(
            status_code=404,
            detail="Order not found",
        )

    # 3. Cross-validate: payment must belong to the given order
    if payment.order_id != order.order_id:
        logger.warning(
            f"Payment {request_data.payment_id} does not belong to "
            f"order {request_data.order_id}"
        )
        raise HTTPException(
            status_code=400,
            detail="Payment does not belong to the specified order",
        )

    # 4. Recompute expected HMAC-SHA256 signature
    message = f"{request_data.order_id}|{request_data.payment_id}"
    expected_signature = hmac.new(
        key=raw_api_secret.encode("utf-8"),
        msg=message.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()

    # 5. Constant-time comparison to prevent timing attacks
    is_valid = hmac.compare_digest(expected_signature, request_data.signature)

    if not is_valid:
        logger.warning(
            f"Signature mismatch for payment={request_data.payment_id} "
            f"order={request_data.order_id}"
        )
        return VerifyPaymentResponse(
            verified=False,
            message="Payment signature verification failed",
        )

    # 6. Update payment and order statuses
    try:
        payment.status = "CAPTURED"
        order.status = "PAID"
        await db_session.commit()
        logger.info(
            f"Payment {request_data.payment_id} verified and captured; "
            f"Order {request_data.order_id} marked as PAID."
        )
    except Exception as e:
        await db_session.rollback()
        logger.error(f"Error updating statuses after verification: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while updating payment status",
        )

    return VerifyPaymentResponse(
        verified=True,
        message="Payment signature is authentic",
    )
