import uuid
from sqlalchemy import BigInteger, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Account(BaseModel):
    """ORM model for Accounts."""

    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    merchant_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("merchants.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )


class LedgerTransaction(BaseModel):
    """ORM model for Ledger Transactions."""

    __tablename__ = "ledger_transactions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source_event: Mapped[str] = mapped_column(String(100), nullable=False)


class LedgerEntry(BaseModel):
    """ORM model for Ledger Entries."""

    __tablename__ = "ledger_entries"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    ledger_transaction_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("ledger_transactions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
