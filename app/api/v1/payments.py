import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_async_db
from app.core.redis import redis_client
from app.dependencies import get_async_db_session, get_merchant_by_api_key
from app.models.merchant import Merchant
from app.schemas.common import GenericResponse
from app.schemas.payment import (
    ProcessPaymentRequest,
    ProcessPaymentResponse,
    VerifyPaymentRequest,
    VerifyPaymentResponse,
)
from app.schemas.refund import RefundCreateRequest, RefundResponse
from app.services.payment_service import (
    process_payment,
    verify_payment_signature,
)
from app.services.refund_service import create_refund

router = APIRouter()
logger = logging.getLogger(__name__)
http_basic = HTTPBasic(auto_error=False)


@router.post(
    "/process", response_model=GenericResponse[ProcessPaymentResponse]
)
async def process_payment_endpoint(
    request: ProcessPaymentRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    db_session: AsyncSession = Depends(get_async_db),
) -> GenericResponse[ProcessPaymentResponse]:
    """
    Process a payment request with idempotency support via Redis.
    """
    redis_key = f"idempotency:payment:{idempotency_key}"

    try:
        # Check if we already processed this idempotency key
        cached_response = await redis_client.get(redis_key)
        if cached_response:
            logger.info(f"Idempotency key hit for {idempotency_key}")
            response_data = json.loads(cached_response)
            return GenericResponse(
                success=True,
                message="Payment already processed (idempotent response)",
                data=ProcessPaymentResponse(**response_data),
            )
    except Exception as e:
        logger.warning(
            f"Redis connection failed, bypassing idempotency check: {e}"
        )

    # Process payment normally
    payment_response = await process_payment(db_session, request)

    try:
        # Cache the successful response for 24 hours (86400 seconds)
        await redis_client.setex(
            redis_key, 86400, payment_response.model_dump_json()
        )
    except Exception as e:
        logger.warning(
            f"Redis connection failed, could not cache response: {e}"
        )

    return GenericResponse(
        success=True,
        message="Payment processed successfully",
        data=payment_response,
    )


@router.post("/verify", response_model=GenericResponse[VerifyPaymentResponse])
async def verify_payment_endpoint(
    request: VerifyPaymentRequest,
    credentials: HTTPBasicCredentials | None = Depends(http_basic),
    merchant: Merchant = Depends(get_merchant_by_api_key),
    db_session: AsyncSession = Depends(get_async_db_session),
) -> GenericResponse[VerifyPaymentResponse]:
    """
    Verify a payment signature submitted by the merchant store backend.

    The merchant authenticates via HTTP Basic Auth (API Key ID : API Secret).
    The submitted signature must equal HMAC-SHA256('order_id|payment_id')
    keyed with the merchant's API secret.

    On successful verification, the payment is marked CAPTURED and the
    order is marked PAID.
    """
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Could not validate API credentials",
            headers={"WWW-Authenticate": "Basic"},
        )

    result = await verify_payment_signature(
        db_session=db_session,
        request_data=request,
        merchant_id=merchant.id,
        raw_api_secret=credentials.password,
    )

    return GenericResponse(
        success=True,
        message=result.message,
        data=result,
    )


@router.post(
    "/{payment_id}/refunds",
    response_model=GenericResponse[RefundResponse],
    status_code=201,
)
async def initiate_refund_endpoint(
    payment_id: str,
    request: RefundCreateRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    merchant: Merchant = Depends(get_merchant_by_api_key),
    db_session: AsyncSession = Depends(get_async_db_session),
) -> GenericResponse[RefundResponse]:
    """
    Initiate a full or partial refund for a specific payment.
    """
    redis_key = f"idempotency:refund:{idempotency_key}"

    try:
        # Check if we already processed this idempotency key
        cached_response = await redis_client.get(redis_key)
        if cached_response:
            logger.info(f"Idempotency key hit for refund {idempotency_key}")
            response_data = json.loads(cached_response)
            return GenericResponse(
                success=True,
                message="Refund already processed (idempotent response)",
                data=RefundResponse(**response_data),
            )
    except Exception as e:
        logger.warning(
            f"Redis connection failed, bypassing idempotency check: {e}"
        )

    # Process refund normally
    refund_response = await create_refund(
        db_session, merchant.id, payment_id, request
    )

    try:
        # Cache the successful response for 24 hours
        await redis_client.setex(
            redis_key, 86400, refund_response.model_dump_json()
        )
    except Exception as e:
        logger.warning(
            f"Redis connection failed, could not cache response: {e}"
        )

    return GenericResponse(
        success=True,
        message="Refund initiated successfully",
        data=refund_response,
    )
