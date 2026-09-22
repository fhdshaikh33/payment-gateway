import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class ApiKey(BaseModel):
    """ORM model for Merchant API Integration Keys."""

    __tablename__ = "api_keys"

    merchant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("merchants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key_id: Mapped[str] = mapped_column(
        String(100), unique=True, index=True, nullable=False
    )
    key_secret_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    environment: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # TEST or LIVE
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
