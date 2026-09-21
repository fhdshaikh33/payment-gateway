import uuid
from typing import Optional

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class Role(BaseModel):
    """Role ORM model."""

    __tablename__ = "roles"

    merchant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("merchants.id", ondelete="CASCADE"), nullable=True
    )  # NULL for default system templates
    name: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # OWNER, DEVELOPER, FINANCE, VIEWER
    description: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
