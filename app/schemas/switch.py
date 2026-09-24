from pydantic import BaseModel, Field

class SubmitOtpRequest(BaseModel):
    payment_id: str = Field(..., description="The ID of the pending payment")
    otp: str = Field(..., description="The 6-digit OTP entered by the user")

class SubmitOtpResponse(BaseModel):
    payment_id: str
    order_id: str
    status: str
    signature: str
