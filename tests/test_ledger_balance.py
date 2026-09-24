"""
Tests for GET /v1/ledger/accounts/balance
"""
import uuid
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.core.security import create_access_token, hash_password
from app.dependencies import get_async_db_session
from app.main import app
from app.models.merchant import Merchant
from app.models.user import User
from app.models.merchant_member import MerchantMember
from app.models.role import Role
from app.models.ledger import Account, LedgerTransaction, LedgerEntry

TEST_ASYNC_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest_asyncio.fixture
async def async_test_session():
    engine = create_async_engine(
        TEST_ASYNC_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def merchant_and_user_token(async_test_session):
    """
    Sets up a merchant, user with MERCHANT role, and returns JWT token.
    """
    # 1. Create Role
    role = Role(id=uuid.uuid4(), name="MERCHANT")
    async_test_session.add(role)

    # 2. Create Merchant
    merchant = Merchant(
        id=uuid.uuid4(),
        business_name="Ledger Test Store",
        legal_entity_type="PVT_LTD",
    )
    async_test_session.add(merchant)

    # 3. Create User
    user = User(
        id=uuid.uuid4(),
        email="ledger@teststore.com",
        password_hash=hash_password("Secure123!"),
        full_name="Ledger Owner",
        is_active=True,
    )
    async_test_session.add(user)

    # 4. Associate User with Merchant
    member = MerchantMember(
        merchant_id=merchant.id,
        user_id=user.id,
        role_id=role.id,
    )
    async_test_session.add(member)
    
    await async_test_session.commit()
    await async_test_session.refresh(merchant)
    await async_test_session.refresh(user)
    await async_test_session.refresh(role)

    # Generate JWT
    access_token = create_access_token(
        subject=str(user.id),
        extra_claims={"roles": [role.name]},
    )
    
    return {
        "merchant_id": merchant.id,
        "user_id": user.id,
        "token": access_token
    }


@pytest.mark.asyncio
async def test_empty_balance(async_test_session, merchant_and_user_token):
    ctx = merchant_and_user_token

    async def override_db():
        yield async_test_session

    app.dependency_overrides[get_async_db_session] = override_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get(
                "/api/v1/ledger/accounts/balance",
                headers={"Authorization": f"Bearer {ctx['token']}"}
            )

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["current_balance"] == 0
        assert data["pending_settlement"] == 0
        assert data["account_name"] == "MERCHANT_WALLET"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_aggregated_balance(async_test_session, merchant_and_user_token):
    ctx = merchant_and_user_token
    
    # Create Account and Ledger Entries
    account = Account(
        merchant_id=ctx["merchant_id"],
        name="MERCHANT_WALLET"
    )
    async_test_session.add(account)
    await async_test_session.commit()
    
    txn1 = LedgerTransaction(source_event="PAYMENT_CAPTURED")
    txn2 = LedgerTransaction(source_event="REFUND_PROCESSED")
    async_test_session.add_all([txn1, txn2])
    await async_test_session.commit()
    
    entry1 = LedgerEntry(
        ledger_transaction_id=txn1.id,
        account_id=account.id,
        amount=50000 # +500
    )
    entry2 = LedgerEntry(
        ledger_transaction_id=txn2.id,
        account_id=account.id,
        amount=-10000 # -100
    )
    async_test_session.add_all([entry1, entry2])
    await async_test_session.commit()
    
    async def override_db():
        yield async_test_session

    app.dependency_overrides[get_async_db_session] = override_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get(
                "/api/v1/ledger/accounts/balance",
                headers={"Authorization": f"Bearer {ctx['token']}"}
            )

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["current_balance"] == 40000 # 50000 - 10000
    finally:
        app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_unauthorized():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get(
            "/api/v1/ledger/accounts/balance",
            headers={"Authorization": "Bearer invalid_token"}
        )
    assert resp.status_code == 401
