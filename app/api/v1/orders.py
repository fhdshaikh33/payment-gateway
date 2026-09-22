from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_async_db_session, get_merchant_by_api_key
from app.models.merchant import Merchant
from app.schemas.common import GenericResponse
from app.schemas.order import OrderCreate, OrderResponse
from app.services import order_service

router = APIRouter()


@router.post(
    "",
    response_model=GenericResponse[OrderResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create Order",
    description="Create a new order for a merchant.",
)
async def create_order_endpoint(
    order_in: OrderCreate,
    current_merchant: Merchant = Depends(get_merchant_by_api_key),
    db: AsyncSession = Depends(get_async_db_session),
) -> GenericResponse[OrderResponse]:
    order = await order_service.create_order(
        db_session=db, merchant_id=current_merchant.id, order_data=order_in
    )

    return GenericResponse(
        success=True,
        message="Order created successfully",
        data=OrderResponse.model_validate(order),
    )
