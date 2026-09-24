"""
Tests for POST /v1/payments/{payment_id}/refunds
"""
import pytest
import pytest_asyncio
import secrets
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.core.security import generate_api_key_pair
from app.dependencies import get_async_db_session
from app.main import app
from app.models.api_key import ApiKey
from app.models.order import Order
from app.models.payment import Payment
from app.schemas.merchant import MerchantRegisterRequest
from app.services.merchant_service import MerchantService

TEST_ASYNC_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def async_test_session():
    """Async SQLite in-memory session fixture, recreated for each test."""
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
async def merchant_with_key(async_test_session):
    """
    Register a merchant and generate an API key.
    """
    reg_req = MerchantRegisterRequest(
        business_name="Refund Test Store",
        legal_entity_type="PVT_LTD",
        full_name="Refund Owner",
        email="refund@teststore.com",
        password="SecurePassword123!",
    )
    reg_resp = await MerchantService.register_merchant(async_test_session, reg_req)

    key_id, key_secret, key_secret_encrypted = generate_api_key_pair("TEST")

    api_key = ApiKey(
        merchant_id=reg_resp.merchant_id,
        key_id=key_id,
        key_secret_encrypted=key_secret_encrypted,
        environment="TEST",
        is_active=True,
    )
    async_test_session.add(api_key)
    await async_test_session.commit()

    return {
        "merchant_id": reg_resp.merchant_id,
        "key_id": key_id,
        "key_secret": key_secret,
    }


@pytest_asyncio.fixture
async def payment_record(async_test_session, merchant_with_key):
    """
    Create a Payment (CAPTURED) linked to the test merchant.
    """
    merchant_id = merchant_with_key["merchant_id"]
    order_id = f"order_{secrets.token_hex(7)}"
    payment_id = f"pay_{secrets.token_hex(7)}"

    order = Order(
        merchant_id=merchant_id,
        order_id=order_id,
        amount=10000,
        currency="INR",
        status="PAID",
    )
    async_test_session.add(order)
    
    payment = Payment(
        payment_id=payment_id,
        order_id=order_id,
        merchant_id=merchant_id,
        amount=10000,
        currency="INR",
        status="CAPTURED",
        method="CARD",
    )
    async_test_session.add(payment)
    await async_test_session.commit()
    await async_test_session.refresh(payment)

    return {
        "payment_id": payment_id,
        "merchant_id": merchant_id,
        "key_id": merchant_with_key["key_id"],
        "key_secret": merchant_with_key["key_secret"],
        "amount": 10000,
    }

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_valid_full_refund(async_test_session, payment_record):
    """A valid full refund request should return 201 Created."""
    ctx = payment_record

    async def override_db():
        yield async_test_session

    app.dependency_overrides[get_async_db_session] = override_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                f"/api/v1/payments/{ctx['payment_id']}/refunds",
                json={"amount": ctx["amount"], "reason": "Customer requested full refund"},
                headers={"Idempotency-Key": f"idem_{secrets.token_hex(4)}"},
                auth=(ctx["key_id"], ctx["key_secret"]),
            )

        assert resp.status_code == 201
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["amount"] == ctx["amount"]
        assert body["data"]["status"] == "PROCESSED"
        assert body["data"]["payment_id"] == ctx["payment_id"]
        assert "refund_id" in body["data"]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_valid_partial_refund(async_test_session, payment_record):
    """A valid partial refund request should return 201 Created."""
    ctx = payment_record

    async def override_db():
        yield async_test_session

    app.dependency_overrides[get_async_db_session] = override_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                f"/api/v1/payments/{ctx['payment_id']}/refunds",
                json={"amount": 5000, "reason": "Customer requested partial refund"},
                headers={"Idempotency-Key": f"idem_{secrets.token_hex(4)}"},
                auth=(ctx["key_id"], ctx["key_secret"]),
            )

        assert resp.status_code == 201
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["amount"] == 5000
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_refund_exceeds_amount(async_test_session, payment_record):
    """Refunding more than the payment amount should return 400 Bad Request."""
    ctx = payment_record

    async def override_db():
        yield async_test_session

    app.dependency_overrides[get_async_db_session] = override_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                f"/api/v1/payments/{ctx['payment_id']}/refunds",
                json={"amount": ctx["amount"] + 100, "reason": "Too much refund"},
                headers={"Idempotency-Key": f"idem_{secrets.token_hex(4)}"},
                auth=(ctx["key_id"], ctx["key_secret"]),
            )

        assert resp.status_code == 400
        assert resp.json()["detail"] == "Refund amount exceeds total payment amount"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_idempotency(async_test_session, payment_record):
    """Sending the same idempotency key twice should return the same response."""
    ctx = payment_record

    async def override_db():
        yield async_test_session

    app.dependency_overrides[get_async_db_session] = override_db

    try:
        idem_key = f"idem_{secrets.token_hex(4)}"
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # First request
            resp1 = await ac.post(
                f"/api/v1/payments/{ctx['payment_id']}/refunds",
                json={"amount": 1000, "reason": "Idempotent refund"},
                headers={"Idempotency-Key": idem_key},
                auth=(ctx["key_id"], ctx["key_secret"]),
            )
            assert resp1.status_code == 201

            # Second request with SAME idempotency key
            resp2 = await ac.post(
                f"/api/v1/payments/{ctx['payment_id']}/refunds",
                json={"amount": 1000, "reason": "Idempotent refund"},
                headers={"Idempotency-Key": idem_key},
                auth=(ctx["key_id"], ctx["key_secret"]),
            )
            assert resp2.status_code == 201
            assert resp2.json()["data"]["refund_id"] == resp1.json()["data"]["refund_id"]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_unauthorized(async_test_session, payment_record):
    """Invalid API credentials should return 401."""
    ctx = payment_record

    async def override_db():
        yield async_test_session

    app.dependency_overrides[get_async_db_session] = override_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                f"/api/v1/payments/{ctx['payment_id']}/refunds",
                json={"amount": 1000, "reason": "Unauthorized refund"},
                headers={"Idempotency-Key": f"idem_{secrets.token_hex(4)}"},
                auth=(ctx["key_id"], "wrong_secret"),
            )

        assert resp.status_code == 401
    finally:
        app.dependency_overrides.clear()
