import uuid
from typing import Sequence

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_async_db_session, get_merchant_by_api_key
from app.models.merchant import Merchant
from app.schemas.webhook import (
    WebhookDeliveryResponse,
    WebhookEndpointCreate,
    WebhookEndpointResponse,
    WebhookEndpointSecretResponse,
    WebhookEndpointUpdate,
)
from app.services import webhook_service

router = APIRouter()


@router.post(
    "/endpoints",
    response_model=WebhookEndpointSecretResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_webhook_endpoint(
    data: WebhookEndpointCreate,
    merchant: Merchant = Depends(get_merchant_by_api_key),
    db: AsyncSession = Depends(get_async_db_session),
):
    """Register a new webhook endpoint for the merchant."""
    endpoint, raw_secret = await webhook_service.register_webhook(
        db, merchant.id, data
    )
    return {
        **endpoint.__dict__,
        "secret": raw_secret,
        "url": str(endpoint.url),  # Handle HttpUrl from Pydantic if needed
    }


@router.get("/endpoints", response_model=list[WebhookEndpointResponse])
async def list_webhook_endpoints(
    merchant: Merchant = Depends(get_merchant_by_api_key),
    db: AsyncSession = Depends(get_async_db_session),
):
    """List all webhook endpoints registered by the merchant."""
    endpoints = await webhook_service.list_webhooks(db, merchant.id)
    return endpoints


@router.get("/endpoints/{endpoint_id}", response_model=WebhookEndpointResponse)
async def get_webhook_endpoint(
    endpoint_id: uuid.UUID,
    merchant: Merchant = Depends(get_merchant_by_api_key),
    db: AsyncSession = Depends(get_async_db_session),
):
    """Get details of a specific webhook endpoint."""
    return await webhook_service.get_webhook(db, merchant.id, endpoint_id)


@router.patch(
    "/endpoints/{endpoint_id}",
    response_model=WebhookEndpointSecretResponse | WebhookEndpointResponse,
)
async def update_webhook_endpoint(
    endpoint_id: uuid.UUID,
    data: WebhookEndpointUpdate,
    merchant: Merchant = Depends(get_merchant_by_api_key),
    db: AsyncSession = Depends(get_async_db_session),
):
    """Update a webhook endpoint (e.g., enable/disable, change events, rotate secret)."""
    endpoint, new_secret = await webhook_service.update_webhook(
        db, merchant.id, endpoint_id, data
    )
    
    if new_secret:
        return {**endpoint.__dict__, "secret": new_secret, "url": str(endpoint.url)}
    return endpoint


@router.delete(
    "/endpoints/{endpoint_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_webhook_endpoint(
    endpoint_id: uuid.UUID,
    merchant: Merchant = Depends(get_merchant_by_api_key),
    db: AsyncSession = Depends(get_async_db_session),
):
    """Permanently delete a webhook endpoint."""
    await webhook_service.delete_webhook(db, merchant.id, endpoint_id)


@router.get(
    "/endpoints/{endpoint_id}/deliveries",
    response_model=list[WebhookDeliveryResponse],
)
async def list_webhook_deliveries(
    endpoint_id: uuid.UUID,
    merchant: Merchant = Depends(get_merchant_by_api_key),
    db: AsyncSession = Depends(get_async_db_session),
):
    """Get the 50 most recent delivery logs for this endpoint."""
    deliveries = await webhook_service.list_deliveries(db, merchant.id, endpoint_id)
    return deliveries


@router.post(
    "/endpoints/{endpoint_id}/test",
    status_code=status.HTTP_202_ACCEPTED,
)
async def send_test_webhook(
    endpoint_id: uuid.UUID,
    merchant: Merchant = Depends(get_merchant_by_api_key),
    db: AsyncSession = Depends(get_async_db_session),
):
    """Send a test 'ping' event to the specified endpoint."""
    # Ensure it exists
    await webhook_service.get_webhook(db, merchant.id, endpoint_id)
    
    import asyncio
    asyncio.create_task(
        webhook_service.dispatch_webhook(
            db,
            merchant.id,
            "ping",
            {"message": "Test webhook delivery from Payment Gateway"},
        )
    )
    return {"message": "Test event dispatched"}
