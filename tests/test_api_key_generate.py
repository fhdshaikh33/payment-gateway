import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.dependencies import get_async_db_session, get_current_active_user
from app.main import app
from app.models.api_key import ApiKey
from app.schemas.merchant import MerchantRegisterRequest
from app.services.merchant_service import MerchantService

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


def test_api_key_generate_route_registered():
    """Verify endpoint is registered in FastAPI app routes."""
    paths = {route.path for route in app.routes}
    assert "/api/v1/merchants/keys/generate" in paths


@pytest.mark.asyncio
async def test_successful_api_key_generation_test_env(async_test_session):
    """Test generating a TEST environment API key for a registered merchant."""
    # Register merchant
    reg_req = MerchantRegisterRequest(
        business_name="Test Store LLC",
        legal_entity_type="PVT_LTD",
        full_name="Bob Admin",
        email="bob@teststore.com",
        password="SecurePassword123!",
    )
    reg_resp = await MerchantService.register_merchant(
        async_test_session, reg_req
    )

    async def override_get_async_db():
        yield async_test_session

    async def override_get_current_active_user():
        return {
            "sub": str(reg_resp.user_id),
            "merchant_id": str(reg_resp.merchant_id),
        }

    app.dependency_overrides[get_async_db_session] = override_get_async_db
    app.dependency_overrides[get_current_active_user] = (
        override_get_current_active_user
    )

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as ac:
            payload = {"environment": "TEST"}
            resp = await ac.post(
                "/api/v1/merchants/keys/generate", json=payload
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["success"] is True
            data = body["data"]
            assert data["key_id"].startswith("rzp_test_")
            assert data["key_secret"].startswith("sec_")
            assert data["environment"] == "TEST"
            assert data["is_active"] is True
            assert "created_at" in data
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_successful_api_key_generation_live_env(async_test_session):
    """Test generating a LIVE environment API key."""
    reg_req = MerchantRegisterRequest(
        business_name="Live Store LLC",
        legal_entity_type="INDIVIDUAL",
        full_name="Alice Live",
        email="alice@livestore.com",
        password="SecurePassword123!",
    )
    reg_resp = await MerchantService.register_merchant(
        async_test_session, reg_req
    )

    async def override_get_async_db():
        yield async_test_session

    async def override_get_current_active_user():
        return {
            "sub": str(reg_resp.user_id),
            "merchant_id": str(reg_resp.merchant_id),
        }

    app.dependency_overrides[get_async_db_session] = override_get_async_db
    app.dependency_overrides[get_current_active_user] = (
        override_get_current_active_user
    )

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as ac:
            payload = {"environment": "LIVE"}
            resp = await ac.post(
                "/api/v1/merchants/keys/generate", json=payload
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["success"] is True
            data = body["data"]
            assert data["key_id"].startswith("rzp_live_")
            assert data["key_secret"].startswith("sec_")
            assert data["environment"] == "LIVE"
            assert data["is_active"] is True
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_api_key_rotation(async_test_session):
    """Test key rotation deactivates previous key and issues new active key."""
    reg_req = MerchantRegisterRequest(
        business_name="Rotate Store Inc",
        legal_entity_type="LLP",
        full_name="Charlie Rotate",
        email="charlie@rotatestore.com",
        password="SecurePassword123!",
    )
    reg_resp = await MerchantService.register_merchant(
        async_test_session, reg_req
    )

    async def override_get_async_db():
        yield async_test_session

    async def override_get_current_active_user():
        return {
            "sub": str(reg_resp.user_id),
            "merchant_id": str(reg_resp.merchant_id),
        }

    app.dependency_overrides[get_async_db_session] = override_get_async_db
    app.dependency_overrides[get_current_active_user] = (
        override_get_current_active_user
    )

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as ac:
            payload = {"environment": "TEST"}

            # First Key Generation
            resp1 = await ac.post(
                "/api/v1/merchants/keys/generate", json=payload
            )
            assert resp1.status_code == 200
            key1_id = resp1.json()["data"]["key_id"]

            # Second Key Generation (Rotation)
            resp2 = await ac.post(
                "/api/v1/merchants/keys/generate", json=payload
            )
            assert resp2.status_code == 200
            key2_id = resp2.json()["data"]["key_id"]

            assert key1_id != key2_id

            # Verify in DB that key1 is deactivated (revoked) and key2 is active
            stmt = select(ApiKey).where(
                ApiKey.merchant_id == reg_resp.merchant_id
            )
            db_keys = (await async_test_session.execute(stmt)).scalars().all()
            assert len(db_keys) == 2

            key1_db = next(k for k in db_keys if k.key_id == key1_id)
            key2_db = next(k for k in db_keys if k.key_id == key2_id)

            assert key1_db.is_active is False
            assert key1_db.revoked_at is not None
            assert key2_db.is_active is True
            assert key2_db.revoked_at is None
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_api_key_invalid_environment(async_test_session):
    """Test error response for invalid environment payload."""

    async def override_get_async_db():
        yield async_test_session

    async def override_get_current_active_user():
        return {"sub": "00000000-0000-0000-0000-000000000000"}

    app.dependency_overrides[get_async_db_session] = override_get_async_db
    app.dependency_overrides[get_current_active_user] = (
        override_get_current_active_user
    )

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as ac:
            payload = {"environment": "INVALID_ENV"}
            resp = await ac.post(
                "/api/v1/merchants/keys/generate", json=payload
            )
            assert resp.status_code == 422
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_api_key_no_merchant_association(async_test_session):
    """Test 403 error when user has no associated merchant."""

    async def override_get_async_db():
        yield async_test_session

    async def override_get_current_active_user():
        return {"sub": "00000000-0000-0000-0000-000000000000"}

    app.dependency_overrides[get_async_db_session] = override_get_async_db
    app.dependency_overrides[get_current_active_user] = (
        override_get_current_active_user
    )

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as ac:
            payload = {"environment": "TEST"}
            resp = await ac.post(
                "/api/v1/merchants/keys/generate", json=payload
            )
            assert resp.status_code == 403
            assert (
                resp.json()["detail"]
                == "No active merchant association found for current user session"
            )
    finally:
        app.dependency_overrides.clear()
