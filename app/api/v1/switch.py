from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_db
from app.schemas.common import GenericResponse
from app.schemas.switch import SubmitOtpRequest, SubmitOtpResponse
from app.services.switch_service import verify_mock_3ds_otp

router = APIRouter()

@router.post("/mock-3ds/submit-otp", response_model=GenericResponse[SubmitOtpResponse])
async def mock_3ds_submit_otp(
    request: SubmitOtpRequest,
    db_session: AsyncSession = Depends(get_async_db),
) -> GenericResponse[SubmitOtpResponse]:
    """
    Mock Bank Switch: Verify 3DS OTP and process the payment capture.
    """
    result = await verify_mock_3ds_otp(session=db_session, request=request)
    return GenericResponse(
        success=True,
        message="OTP verified successfully",
        data=result
    )
