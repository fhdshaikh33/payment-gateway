import logging
import secrets

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import Payment
from app.repositories.api_key_repository import ApiKeyRepository
from app.schemas.payment import ProcessPaymentRequest, ProcessPaymentResponse
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
