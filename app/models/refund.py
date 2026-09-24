import uuid
from sqlalchemy import ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Refund(BaseModel):
    """ORM model for Refunds."""

    __tablename__ = "refunds"

    refund_id: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False
    )
    payment_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("payments.payment_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("merchants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="PROCESSED", nullable=False
    )
