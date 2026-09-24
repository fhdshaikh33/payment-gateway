import hashlib
import hmac

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decrypt_api_secret
from app.models.api_key import ApiKey
from app.models.order import Order
from app.models.payment import Payment
from app.schemas.switch import SubmitOtpRequest, SubmitOtpResponse


async def verify_mock_3ds_otp(
    session: AsyncSession, request: SubmitOtpRequest
) -> SubmitOtpResponse:
    """
    Process Mock 3DS OTP submission.
    No repository layer used. Performs direct SQL queries.
    """
    
    # 1. Fetch Payment
    stmt_payment = select(Payment).where(Payment.payment_id == request.payment_id)
    result_payment = await session.execute(stmt_payment)
    payment = result_payment.scalars().first()
    
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
        
    if payment.status != "PENDING":
        raise HTTPException(
            status_code=400, detail=f"Payment cannot be captured. Current status: {payment.status}"
        )

    # 2. Verify OTP
    if request.otp != "123456":
        # Simulate failed auth
        payment.status = "FAILED"
        await session.commit()
        raise HTTPException(status_code=400, detail="Invalid OTP. Authentication failed.")
        
    # 3. Update Payment Status
    payment.status = "CAPTURED"
    
    # 4. Fetch associated Order
    stmt_order = select(Order).where(Order.order_id == payment.order_id)
    result_order = await session.execute(stmt_order)
    order = result_order.scalars().first()
    
    if not order:
        raise HTTPException(status_code=404, detail="Associated order not found")
        
    # Update Order Status
    order.status = "PAID"
    
    # 5. Fetch ApiKey to get encrypted secret
    # Assuming the payment used a specific environment, we should find an active key for this merchant
    # Ideally we'd link the specific key_id used to the payment, but for this demo we'll fetch any active key
    stmt_key = select(ApiKey).where(
        ApiKey.merchant_id == payment.merchant_id,
        ApiKey.is_active.is_(True)
    ).limit(1)
    
    result_key = await session.execute(stmt_key)
    api_key = result_key.scalars().first()
    
    if not api_key:
        raise HTTPException(status_code=500, detail="Merchant API key not found")
        
    # 6. Generate HMAC-SHA256 signature
    decrypted_secret = decrypt_api_secret(api_key.key_secret_encrypted)
    
    payload_str = f"{order.order_id}|{payment.payment_id}"
    
    signature = hmac.new(
        key=decrypted_secret.encode('utf-8'),
        msg=payload_str.encode('utf-8'),
        digestmod=hashlib.sha256
    ).hexdigest()
    
    # 7. Commit changes
    await session.commit()
    
    return SubmitOtpResponse(
        payment_id=payment.payment_id,
        order_id=order.order_id,
        status=payment.status,
        signature=signature
    )
