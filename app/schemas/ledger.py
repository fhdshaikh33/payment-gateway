from datetime import datetime
import uuid
from pydantic import BaseModel


class LedgerBalanceResponse(BaseModel):
    account_id: uuid.UUID
    account_name: str
    currency: str
    current_balance: int
    pending_settlement: int
    updated_at: datetime


class LedgerLegSchema(BaseModel):
    account: str
    direction: str
    amount: int


class LedgerTransactionResponse(BaseModel):
    transaction_id: uuid.UUID
    source_event: str
    reference_id: str
    legs: list[LedgerLegSchema]
    is_balanced: bool
