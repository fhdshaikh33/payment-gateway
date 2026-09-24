from datetime import datetime
from pydantic import BaseModel, Field


class RefundCreateRequest(BaseModel):
    amount: int = Field(..., gt=0, description="Refund amount in smallest currency unit")
    reason: str = Field(..., max_length=255, description="Reason for refund")


class RefundResponse(BaseModel):
    refund_id: str
    payment_id: str
    amount: int
    currency: str
    status: str
    created_at: datetime
