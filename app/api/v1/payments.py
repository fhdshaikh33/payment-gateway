import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_async_db
from app.core.redis import redis_client
from app.schemas.common import GenericResponse
from app.schemas.payment import ProcessPaymentRequest, ProcessPaymentResponse
from app.services.payment_service import process_payment

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/process", response_model=GenericResponse[ProcessPaymentResponse])
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
                data=ProcessPaymentResponse(**response_data)
            )
    except Exception as e:
        logger.warning(f"Redis connection failed, bypassing idempotency check: {e}")

    # Process payment normally
    payment_response = await process_payment(db_session, request)

    try:
        # Cache the successful response for 24 hours (86400 seconds)
        await redis_client.setex(
            redis_key,
            86400,
            payment_response.model_dump_json()
        )
    except Exception as e:
        logger.warning(f"Redis connection failed, could not cache response: {e}")

    return GenericResponse(
        success=True,
        message="Payment processed successfully",
        data=payment_response
    )
