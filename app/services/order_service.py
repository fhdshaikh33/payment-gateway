import secrets
import uuid

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order
from app.schemas.order import OrderCreate

async def create_order(
    db_session: AsyncSession,
    merchant_id: uuid.UUID,
    order_data: OrderCreate,
) -> Order:
    """Create a new order directly in the database."""
    random_hex = secrets.token_hex(7)
    order_id = f"order_{random_hex}"

    new_order = Order(
        merchant_id=merchant_id,
        order_id=order_id,
        amount=order_data.amount,
        currency=order_data.currency.upper(),
        receipt=order_data.receipt,
        notes=order_data.notes,
        status="CREATED",
    )
    db_session.add(new_order)
    await db_session.commit()
    await db_session.refresh(new_order)                                       

    return new_order


async def get_order_by_public_id(
    db_session: AsyncSession, order_id: str, merchant_id: uuid.UUID
) -> Optional[Order]:
    """Fetch an order by its public ID and associated merchant ID."""
    stmt = select(Order).where(
        Order.order_id == order_id,
        Order.merchant_id == merchant_id,
    )
    result = await db_session.execute(stmt)
    return result.scalars().first()
