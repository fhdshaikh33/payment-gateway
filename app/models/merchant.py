from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class Merchant(BaseModel):
    """Merchant ORM model."""

    __tablename__ = "merchants"

    business_name: Mapped[str] = mapped_column(String(255), nullable=False)
    legal_entity_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # INDIVIDUAL, PVT_LTD, LLP
    kyc_status: Mapped[str] = mapped_column(
        String(50), default="PENDING", nullable=False
    )  # PENDING, APPROVED, REJECTED
