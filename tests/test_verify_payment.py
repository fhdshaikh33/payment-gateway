"""
Tests for POST /v1/payments/verify — Payment Signature Verification

Test cases covered:
  - Valid signature → 200 OK, verified: true
  - Tampered signature → 200 OK, verified: false
  - Non-existent payment_id → 404
  - Non-existent order_id → 404
  - order_id / payment_id mismatch → 400
  - Invalid Basic Auth credentials → 401
  - Signature wrong length → 422 (Pydantic validation)
"""

import hashlib
import hmac
import secrets

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
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
    """Async SQLite in-memory session, with JSONB→JSON remapping for SQLite."""
    engine = create_async_engine(
        TEST_ASYNC_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Remap JSONB → JSON before DDL is emitted

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Remove listener so it doesn't affect other test modules

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
    Register a merchant and generate an API key pair.
    Returns a dict with: merchant_id, key_id, key_secret.
    """
    reg_req = MerchantRegisterRequest(
        business_name="Verify Test Store",
        legal_entity_type="PVT_LTD",
        full_name="Test Owner",
        email="verify@teststore.com",
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
async def order_and_payment(async_test_session, merchant_with_key):
    """
    Create an Order (CREATED) and a Payment (PENDING) for the test merchant.
    Returns a dict with: order_id, payment_id, merchant_id, key_id, key_secret.
    """
    merchant_id = merchant_with_key["merchant_id"]
    order_id = f"order_{secrets.token_hex(7)}"
    payment_id = f"pay_{secrets.token_hex(7)}"

    order = Order(
        merchant_id=merchant_id,
        order_id=order_id,
        amount=50000,
        currency="INR",
        status="CREATED",
    )
    async_test_session.add(order)
    await async_test_session.commit()
    await async_test_session.refresh(order)

    payment = Payment(
        payment_id=payment_id,
        order_id=order_id,
        merchant_id=merchant_id,
        amount=50000,
        currency="INR",
        status="PENDING",
        method="CARD",
    )
    async_test_session.add(payment)
    await async_test_session.commit()
    await async_test_session.refresh(payment)

    return {
        "order_id": order_id,
        "payment_id": payment_id,
        "merchant_id": merchant_id,
        "key_id": merchant_with_key["key_id"],
        "key_secret": merchant_with_key["key_secret"],
    }


def make_signature(order_id: str, payment_id: str, api_secret: str) -> str:
    """Compute HMAC-SHA256 signature (mirrors gateway logic)."""
    message = f"{order_id}|{payment_id}"
    return hmac.new(
        key=api_secret.encode("utf-8"),
        msg=message.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()


# ---------------------------------------------------------------------------
# Route registration smoke test
# ---------------------------------------------------------------------------


def test_verify_payment_route_registered():
    """Confirm the /verify endpoint is registered in the FastAPI app."""
    paths = {route.path for route in app.routes}
    assert "/api/v1/payments/verify" in paths


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_valid_signature_returns_verified_true(
    async_test_session, order_and_payment
):
    """A correctly computed signature should return verified=true."""
    ctx = order_and_payment
    signature = make_signature(ctx["order_id"], ctx["payment_id"], ctx["key_secret"])

    async def override_db():
        yield async_test_session

    app.dependency_overrides[get_async_db_session] = override_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/api/v1/payments/verify",
                json={
                    "order_id": ctx["order_id"],
                    "payment_id": ctx["payment_id"],
                    "signature": signature,
                },
                auth=(ctx["key_id"], ctx["key_secret"]),
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["verified"] is True
        assert body["data"]["message"] == "Payment signature is authentic"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tampered signature
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tampered_signature_returns_verified_false(
    async_test_session, order_and_payment
):
    """A tampered signature (wrong 64-char hex) should return verified=false with 200."""
    ctx = order_and_payment
    bad_signature = "a" * 64

    async def override_db():
        yield async_test_session

    app.dependency_overrides[get_async_db_session] = override_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/api/v1/payments/verify",
                json={
                    "order_id": ctx["order_id"],
                    "payment_id": ctx["payment_id"],
                    "signature": bad_signature,
                },
                auth=(ctx["key_id"], ctx["key_secret"]),
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["verified"] is False
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Non-existent payment_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_nonexistent_payment_id_returns_404(
    async_test_session, order_and_payment
):
    """A payment_id that doesn't exist should return 404."""
    ctx = order_and_payment
    ghost_payment_id = f"pay_{secrets.token_hex(7)}"
    signature = make_signature(ctx["order_id"], ghost_payment_id, ctx["key_secret"])

    async def override_db():
        yield async_test_session

    app.dependency_overrides[get_async_db_session] = override_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/api/v1/payments/verify",
                json={
                    "order_id": ctx["order_id"],
                    "payment_id": ghost_payment_id,
                    "signature": signature,
                },
                auth=(ctx["key_id"], ctx["key_secret"]),
            )

        assert resp.status_code == 404
        assert resp.json()["detail"] == "Payment not found"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Non-existent order_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_nonexistent_order_id_returns_404(
    async_test_session, order_and_payment
):
    """An order_id that doesn't exist should return 404."""
    ctx = order_and_payment
    ghost_order_id = f"order_{secrets.token_hex(7)}"
    signature = make_signature(ghost_order_id, ctx["payment_id"], ctx["key_secret"])

    async def override_db():
        yield async_test_session

    app.dependency_overrides[get_async_db_session] = override_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/api/v1/payments/verify",
                json={
                    "order_id": ghost_order_id,
                    "payment_id": ctx["payment_id"],
                    "signature": signature,
                },
                auth=(ctx["key_id"], ctx["key_secret"]),
            )

        assert resp.status_code == 404
        assert resp.json()["detail"] == "Order not found"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# order_id / payment_id mismatch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_order_payment_mismatch_returns_400(
    async_test_session, merchant_with_key
):
    """A payment_id belonging to a different order should return 400."""
    merchant_id = merchant_with_key["merchant_id"]

    order_a_id = f"order_{secrets.token_hex(7)}"
    order_b_id = f"order_{secrets.token_hex(7)}"
    payment_b_id = f"pay_{secrets.token_hex(7)}"

    for oid in [order_a_id, order_b_id]:
        async_test_session.add(Order(
            merchant_id=merchant_id,
            order_id=oid,
            amount=10000,
            currency="INR",
            status="CREATED",
        ))

    async_test_session.add(Payment(
        payment_id=payment_b_id,
        order_id=order_b_id,
        merchant_id=merchant_id,
        amount=10000,
        currency="INR",
        status="PENDING",
        method="UPI",
    ))
    await async_test_session.commit()

    # Submit order_a but payment_b → mismatch
    signature = make_signature(order_a_id, payment_b_id, merchant_with_key["key_secret"])

    async def override_db():
        yield async_test_session

    app.dependency_overrides[get_async_db_session] = override_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/api/v1/payments/verify",
                json={
                    "order_id": order_a_id,
                    "payment_id": payment_b_id,
                    "signature": signature,
                },
                auth=(merchant_with_key["key_id"], merchant_with_key["key_secret"]),
            )

        assert resp.status_code == 400
        assert resp.json()["detail"] == "Payment does not belong to the specified order"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Invalid Basic Auth credentials
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invalid_api_credentials_returns_401(
    async_test_session, order_and_payment
):
    """Wrong API secret in Basic Auth should return 401 Unauthorized."""
    ctx = order_and_payment
    signature = make_signature(ctx["order_id"], ctx["payment_id"], ctx["key_secret"])

    async def override_db():
        yield async_test_session

    app.dependency_overrides[get_async_db_session] = override_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/api/v1/payments/verify",
                json={
                    "order_id": ctx["order_id"],
                    "payment_id": ctx["payment_id"],
                    "signature": signature,
                },
                auth=(ctx["key_id"], "totally_wrong_secret"),
            )

        assert resp.status_code == 401
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Signature wrong length — Pydantic validation (422)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_signature_wrong_length_returns_422(
    async_test_session, order_and_payment
):
    """A signature shorter than 64 characters should be rejected by Pydantic (422)."""
    ctx = order_and_payment

    async def override_db():
        yield async_test_session

    app.dependency_overrides[get_async_db_session] = override_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/api/v1/payments/verify",
                json={
                    "order_id": ctx["order_id"],
                    "payment_id": ctx["payment_id"],
                    "signature": "tooshort",
                },
                auth=(ctx["key_id"], ctx["key_secret"]),
            )

        assert resp.status_code == 422
    finally:
        app.dependency_overrides.clear()
