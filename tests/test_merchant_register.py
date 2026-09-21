import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.database import Base
from app.dependencies import get_async_db_session

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

    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


def test_merchant_register_route_registered():
    """Verify endpoint is registered in FastAPI app routes."""
    paths = {route.path for route in app.routes}
    assert "/api/v1/merchants/register" in paths


@pytest.mark.asyncio
async def test_successful_merchant_registration(async_test_session):
    """Test successful merchant registration via service/endpoint logic."""
    async def override_get_async_db():
        yield async_test_session

    app.dependency_overrides[get_async_db_session] = override_get_async_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            payload = {
                "business_name": "Acme Payments LLC",
                "legal_entity_type": "PVT_LTD",
                "full_name": "Alice Merchant",
                "email": "alice@acmepay.com",
                "password": "SecurePassword123!",
            }
            response = await ac.post("/api/v1/merchants/register", json=payload)
            assert response.status_code == 201
            body = response.json()
            assert body["success"] is True
            assert body["message"] == "Merchant registered successfully"
            data = body["data"]
            assert data["business_name"] == "Acme Payments LLC"
            assert data["legal_entity_type"] == "PVT_LTD"
            assert data["kyc_status"] == "PENDING"
            assert data["full_name"] == "Alice Merchant"
            assert data["email"] == "alice@acmepay.com"
            assert "merchant_id" in data
            assert "user_id" in data
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_duplicate_email_merchant_registration(async_test_session):
    """Test duplicate email registration returns 400 error."""
    async def override_get_async_db():
        yield async_test_session

    app.dependency_overrides[get_async_db_session] = override_get_async_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            payload = {
                "business_name": "Acme Payments LLC",
                "legal_entity_type": "PVT_LTD",
                "full_name": "Alice Merchant",
                "email": "duplicate@acmepay.com",
                "password": "SecurePassword123!",
            }
            # First attempt
            resp1 = await ac.post("/api/v1/merchants/register", json=payload)
            assert resp1.status_code == 201

            # Second attempt with same email
            resp2 = await ac.post("/api/v1/merchants/register", json=payload)
            assert resp2.status_code == 400
            assert resp2.json()["detail"] == "Email address is already registered"
    finally:
        app.dependency_overrides.clear()
