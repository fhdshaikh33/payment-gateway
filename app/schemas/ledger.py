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
