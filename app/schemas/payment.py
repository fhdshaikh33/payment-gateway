from typing import Optional
from pydantic import BaseModel, Field, field_validator


class CardDetails(BaseModel):
    number: str
    exp_month: str
    exp_year: str
    cvv: str
    name: str


class ProcessPaymentRequest(BaseModel):
    order_id: str
    key_id: str
    method: str
    card: Optional[CardDetails] = None
    upi_id: Optional[str] = None
    bank_code: Optional[str] = None

    @field_validator("method")
    @classmethod
    def validate_method(cls, v: str) -> str:
        valid_methods = {"CARD", "UPI", "NETBANKING"}
        v_upper = v.upper()
        if v_upper not in valid_methods:
            raise ValueError(f"method must be one of {valid_methods}")
        return v_upper


class ProcessPaymentResponse(BaseModel):
    payment_id: str
    order_id: str
    status: str
    action: Optional[str] = None
    challenge_url: Optional[str] = None


class VerifyPaymentRequest(BaseModel):
    """Request payload for verifying a payment signature."""

    order_id: str = Field(..., min_length=1, description="Public order ID")
    payment_id: str = Field(..., min_length=1, description="Public payment ID")
    signature: str = Field(
        ...,
        min_length=64,
        max_length=64,
        description="HMAC-SHA256 hex digest of 'order_id|payment_id'",
    )


class VerifyPaymentResponse(BaseModel):
    """Response payload for payment signature verification."""

    verified: bool
    message: str
