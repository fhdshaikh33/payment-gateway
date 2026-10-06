import uuid
from typing import Optional
from sqlalchemy import String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class AdminAuditLog(BaseModel):
    """Admin Audit Log ORM model for platform administrative actions."""

    __tablename__ = "admin_audit_logs"

    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, nullable=True)
    user_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
