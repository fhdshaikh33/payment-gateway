from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, HttpUrl


class WebhookEventEnum(str, Enum):
    PAYMENT_CAPTURED = "payment.captured"
    PAYMENT_FAILED = "payment.failed"
    REFUND_CREATED = "refund.created"
    REFUND_COMPLETED = "refund.completed"
    ORDER_EXPIRED = "order.expired"
    PING = "ping"


class WebhookEndpointCreate(BaseModel):
    url: HttpUrl
    events: list[WebhookEventEnum]
    description: str | None = None


class WebhookEndpointUpdate(BaseModel):
    url: HttpUrl | None = None
    events: list[WebhookEventEnum] | None = None
    is_active: bool | None = None
    description: str | None = None
    rotate_secret: bool | None = False


class WebhookEndpointResponse(BaseModel):
    id: UUID
    url: str
    events: list[str]
    is_active: bool
    description: str | None
    created_at: datetime


class WebhookEndpointSecretResponse(WebhookEndpointResponse):
    secret: str


class WebhookDeliveryResponse(BaseModel):
    id: UUID
    event: str
    status: str
    attempt_number: int
    response_status: int | None
    delivered_at: datetime | None
    created_at: datetime
