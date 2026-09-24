import asyncio
import hashlib
import hmac
import json
import logging
import secrets
from datetime import datetime, timezone
from typing import Any, Sequence
from uuid import UUID

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.core.security import decrypt_api_secret, encrypt_api_secret
from app.models.webhook import WebhookDelivery, WebhookEndpoint
from app.schemas.webhook import WebhookEndpointCreate, WebhookEndpointUpdate

logger = logging.getLogger(__name__)

# Exponential backoff retry delays (in seconds)
RETRY_DELAYS = [0, 60, 600, 3600, 21600]  # 0s, 1m, 10m, 1h, 6h


def sign_payload(secret_plaintext: str, body: bytes) -> str:
    """Generate HMAC-SHA256 signature for the webhook payload."""
    signature = hmac.new(
        key=secret_plaintext.encode("utf-8"),
        msg=body,
        digestmod=hashlib.sha256,
    ).hexdigest()
    return f"sha256={signature}"


async def register_webhook(
    db: AsyncSession, merchant_id: UUID, data: WebhookEndpointCreate
) -> tuple[WebhookEndpoint, str]:
    """Register a new webhook endpoint and return it along with the raw secret."""
    raw_secret = f"whsec_{secrets.token_urlsafe(24)}"
    encrypted_secret = encrypt_api_secret(raw_secret)

    endpoint = WebhookEndpoint(
        merchant_id=merchant_id,
        url=str(data.url),
        secret_encrypted=encrypted_secret,
        events=[e.value for e in data.events],
        description=data.description,
    )
    db.add(endpoint)
    await db.commit()
    await db.refresh(endpoint)

    return endpoint, raw_secret


async def list_webhooks(
    db: AsyncSession, merchant_id: UUID
) -> Sequence[WebhookEndpoint]:
    """List all webhook endpoints for a merchant."""
    stmt = select(WebhookEndpoint).where(
        WebhookEndpoint.merchant_id == merchant_id
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_webhook(
    db: AsyncSession, merchant_id: UUID, endpoint_id: UUID
) -> WebhookEndpoint:
    """Get a specific webhook endpoint."""
    stmt = select(WebhookEndpoint).where(
        WebhookEndpoint.merchant_id == merchant_id,
        WebhookEndpoint.id == endpoint_id,
    )
    result = await db.execute(stmt)
    endpoint = result.scalars().first()
    if not endpoint:
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")
    return endpoint


async def update_webhook(
    db: AsyncSession,
    merchant_id: UUID,
    endpoint_id: UUID,
    data: WebhookEndpointUpdate,
) -> tuple[WebhookEndpoint, str | None]:
    """Update a webhook endpoint. Optionally rotates the secret."""
    endpoint = await get_webhook(db, merchant_id, endpoint_id)

    if data.url is not None:
        endpoint.url = str(data.url)
    if data.events is not None:
        endpoint.events = [e.value for e in data.events]
    if data.is_active is not None:
        endpoint.is_active = data.is_active
    if data.description is not None:
        endpoint.description = data.description

    raw_secret = None
    if data.rotate_secret:
        raw_secret = f"whsec_{secrets.token_urlsafe(24)}"
        endpoint.secret_encrypted = encrypt_api_secret(raw_secret)

    await db.commit()
    await db.refresh(endpoint)
    return endpoint, raw_secret


async def delete_webhook(db: AsyncSession, merchant_id: UUID, endpoint_id: UUID) -> None:
    """Hard delete a webhook endpoint."""
    endpoint = await get_webhook(db, merchant_id, endpoint_id)
    await db.delete(endpoint)
    await db.commit()


async def list_deliveries(
    db: AsyncSession, merchant_id: UUID, endpoint_id: UUID
) -> Sequence[WebhookDelivery]:
    """List recent delivery logs for an endpoint."""
    # Ensure endpoint belongs to merchant
    await get_webhook(db, merchant_id, endpoint_id)

    stmt = (
        select(WebhookDelivery)
        .where(WebhookDelivery.endpoint_id == endpoint_id)
        .order_by(WebhookDelivery.created_at.desc())
        .limit(50)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def _deliver(
    endpoint_id: UUID,
    delivery_id: UUID,
    url: str,
    secret_plaintext: str,
    event: str,
    payload: dict[str, Any],
    attempt: int = 1,
) -> None:
    """Deliver a single webhook. Retries on failure."""
    if attempt > len(RETRY_DELAYS):
        logger.error(f"Webhook {delivery_id} permanently failed after {attempt-1} attempts.")
        return

    delay = RETRY_DELAYS[attempt - 1]
    if delay > 0:
        await asyncio.sleep(delay)

    # Use a new DB session for background task
    async with async_session_factory() as session:
        delivery_stmt = select(WebhookDelivery).where(WebhookDelivery.id == delivery_id)
        delivery_result = await session.execute(delivery_stmt)
        delivery = delivery_result.scalars().first()
        
        if not delivery:
            logger.error(f"Webhook delivery {delivery_id} not found.")
            return

        delivery.attempt_number = attempt
        
        body_bytes = json.dumps(payload).encode("utf-8")
        signature = sign_payload(secret_plaintext, body_bytes)
        
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Event": event,
            "X-Webhook-Signature": signature,
            "X-Delivery-ID": str(delivery_id),
        }

        success = False
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, content=body_bytes, headers=headers)
                delivery.response_status = response.status_code
                delivery.response_body = response.text[:1000]

                if response.is_success:
                    delivery.status = "SUCCESS"
                    delivery.delivered_at = datetime.now(timezone.utc)
                    success = True
                else:
                    delivery.status = "FAILED"
                    logger.warning(
                        f"Webhook {delivery_id} failed with status {response.status_code}"
                    )
        except Exception as e:
            delivery.status = "FAILED"
            delivery.response_body = str(e)[:1000]
            logger.warning(f"Webhook {delivery_id} error: {e}")

        await session.commit()

    if not success:
        # Schedule retry in the background
        asyncio.create_task(
            _deliver(
                endpoint_id,
                delivery_id,
                url,
                secret_plaintext,
                event,
                payload,
                attempt + 1,
            )
        )


async def dispatch_webhook(
    db: AsyncSession, merchant_id: UUID, event: str, payload: dict[str, Any]
) -> None:
    """
    Finds active endpoints subscribed to the event and dispatches the payload.
    Should be called via asyncio.create_task from API endpoints.
    """
    # 1. Query active endpoints for this merchant that contain the event
    stmt = select(WebhookEndpoint).where(
        WebhookEndpoint.merchant_id == merchant_id,
        WebhookEndpoint.is_active == True,
    )
    result = await db.execute(stmt)
    endpoints = result.scalars().all()

    for endpoint in endpoints:
        # PostgreSQL ARRAY of strings natively maps to a list
        if event in endpoint.events or not endpoint.events:
            # 2. Create Delivery Record
            delivery = WebhookDelivery(
                endpoint_id=endpoint.id,
                event=event,
                payload=payload,
                status="PENDING",
            )
            db.add(delivery)
            await db.commit()
            await db.refresh(delivery)

            # 3. Decrypt secret for delivery
            secret_plaintext = decrypt_api_secret(endpoint.secret_encrypted)

            # 4. Fire delivery background task
            asyncio.create_task(
                _deliver(
                    endpoint_id=endpoint.id,
                    delivery_id=delivery.id,
                    url=endpoint.url,
                    secret_plaintext=secret_plaintext,
                    event=event,
                    payload=payload,
                )
            )
