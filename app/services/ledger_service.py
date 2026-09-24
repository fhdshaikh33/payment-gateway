import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import HTTPException

from app.core.redis import redis_client
from app.models.ledger import Account, LedgerEntry, LedgerTransaction
from app.schemas.ledger import (
    LedgerBalanceResponse,
    LedgerLegSchema,
    LedgerTransactionResponse,
)

logger = logging.getLogger(__name__)


async def get_merchant_wallet_balance(
    db_session: AsyncSession, merchant_id: uuid.UUID
) -> LedgerBalanceResponse:
    """
    Retrieve the real-time cached aggregate balance for the given merchant's wallet.
    """
    # 1. Fetch Account
    account_stmt = select(Account).where(
        Account.merchant_id == merchant_id,
        Account.name == "MERCHANT_WALLET"
    )
    account_result = await db_session.execute(account_stmt)
    account = account_result.scalars().first()

    if not account:
        logger.info(f"No MERCHANT_WALLET account found for merchant {merchant_id}. Returning 0.")
        return LedgerBalanceResponse(
            account_id=uuid.uuid4(),  # Mock ID since it doesn't exist yet
            account_name="MERCHANT_WALLET",
            currency="INR",
            current_balance=0,
            pending_settlement=0,
            updated_at=datetime.now(timezone.utc),
        )

    redis_key = f"ledger:balance:{account.id}"

    # 2. Check Cache
    try:
        cached_data = await redis_client.get(redis_key)
        if cached_data:
            logger.info(f"Cache hit for account balance {account.id}")
            data_dict = json.loads(cached_data)
            data_dict['account_id'] = uuid.UUID(data_dict['account_id'])
            data_dict['updated_at'] = datetime.fromisoformat(data_dict['updated_at'])
            return LedgerBalanceResponse(**data_dict)
    except Exception as e:
        logger.warning(f"Redis connection failed, bypassing cache for balance: {e}")

    # 3. Calculate Balance (Cache Miss)
    balance_stmt = select(func.sum(LedgerEntry.amount)).where(
        LedgerEntry.account_id == account.id
    )
    balance_result = await db_session.execute(balance_stmt)
    current_balance = balance_result.scalar() or 0

    response = LedgerBalanceResponse(
        account_id=account.id,
        account_name=account.name,
        currency="INR",  # Or fetch from account if we added it
        current_balance=current_balance,
        pending_settlement=current_balance,  # Mock pending_settlement as equal for now
        updated_at=datetime.now(timezone.utc),
    )

    # 4. Set Cache
    try:
        response_dict = response.model_dump()
        response_dict['account_id'] = str(response_dict['account_id'])
        response_dict['updated_at'] = response_dict['updated_at'].isoformat()
        await redis_client.setex(redis_key, 300, json.dumps(response_dict)) # 5 minutes TTL
    except Exception as e:
        logger.warning(f"Redis connection failed, could not cache balance: {e}")

    return response


async def get_ledger_transaction_by_reference(
    db_session: AsyncSession, reference_id: str
) -> LedgerTransactionResponse:
    """
    Retrieve the ledger transaction and its legs by the given reference ID.
    """
    # 1. Fetch LedgerTransaction by reference_id
    transaction_stmt = select(LedgerTransaction).where(
        LedgerTransaction.reference_id == reference_id
    )
    transaction_result = await db_session.execute(transaction_stmt)
    transaction = transaction_result.scalars().first()

    if not transaction:
        logger.info(f"Ledger transaction with reference_id {reference_id} not found.")
        raise HTTPException(status_code=404, detail="Ledger transaction not found")

    # 2. Fetch LedgerEntries + Accounts
    entries_stmt = select(LedgerEntry, Account).join(
        Account, LedgerEntry.account_id == Account.id
    ).where(
        LedgerEntry.ledger_transaction_id == transaction.id
    )
    entries_result = await db_session.execute(entries_stmt)
    rows = entries_result.all()

    legs = []
    total_balance = 0

    for entry, account in rows:
        amount = entry.amount
        total_balance += amount

        direction = "CREDIT" if amount >= 0 else "DEBIT"
        
        legs.append(LedgerLegSchema(
            account=account.name,
            direction=direction,
            amount=abs(amount)
        ))

    return LedgerTransactionResponse(
        transaction_id=transaction.id,
        source_event=transaction.source_event,
        reference_id=transaction.reference_id,
        legs=legs,
        is_balanced=(total_balance == 0)
    )
