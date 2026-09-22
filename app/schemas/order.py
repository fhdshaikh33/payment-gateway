from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class OrderCreate(BaseModel):
    amount: int = Field(..., gt=0, description="Amount in smallest currency unit")
    currency: str = Field(..., min_length=3, max_length=3)
    receipt: Optional[str] = None
    notes: Optional[dict] = None


class OrderResponse(BaseModel):
    order_id: str
    amount: int
    currency: str
    receipt: Optional[str] = None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True
