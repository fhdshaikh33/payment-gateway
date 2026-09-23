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
