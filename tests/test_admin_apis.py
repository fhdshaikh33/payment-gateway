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
from app.models.role import Role
from app.models.user import User

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
async def admin_auth(async_test_session):
    admin_user = User(
        id=uuid.uuid4(),
        email="admin@platform.com",
        password_hash=hash_password("AdminPass123!"),
        full_name="Platform Administrator",
        is_active=True,
    )
    async_test_session.add(admin_user)

    merchant = Merchant(
        id=uuid.uuid4(),
        business_name="Acme Corp Test",
        legal_entity_type="PVT_LTD",
        kyc_status="PENDING",
    )
    async_test_session.add(merchant)
    await async_test_session.commit()

    token = create_access_token(
        subject=str(admin_user.id),
        extra_claims={"roles": ["PLATFORM_ADMIN"], "email": admin_user.email},
    )

    return {
        "admin_id": admin_user.id,
        "token": token,
        "merchant_id": merchant.id,
    }


@pytest.mark.asyncio
async def test_list_merchants(async_test_session, admin_auth):
    ctx = admin_auth

    async def override_db():
        yield async_test_session

    app.dependency_overrides[get_async_db_session] = override_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get(
                "/api/v1/admin/merchants",
                headers={"Authorization": f"Bearer {ctx['token']}"},
            )

        assert resp.status_code == 200
        res_json = resp.json()
        assert res_json["success"] is True
        assert res_json["data"]["total"] >= 1
        data_items = res_json["data"]["data"]
        assert any(item["business_name"] == "Acme Corp Test" for item in data_items)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_merchant_detail(async_test_session, admin_auth):
    ctx = admin_auth

    async def override_db():
        yield async_test_session

    app.dependency_overrides[get_async_db_session] = override_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get(
                f"/api/v1/admin/merchants/{ctx['merchant_id']}",
                headers={"Authorization": f"Bearer {ctx['token']}"},
            )

        assert resp.status_code == 200
        res_json = resp.json()
        assert res_json["success"] is True
        data = res_json["data"]
        assert data["merchant_id"] == str(ctx["merchant_id"])
        assert data["business_name"] == "Acme Corp Test"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_update_merchant_status_and_kyc(async_test_session, admin_auth):
    ctx = admin_auth

    async def override_db():
        yield async_test_session

    app.dependency_overrides[get_async_db_session] = override_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # 1. Update Status to APPROVED
            resp = await ac.patch(
                f"/api/v1/admin/merchants/{ctx['merchant_id']}/status",
                headers={"Authorization": f"Bearer {ctx['token']}"},
                json={"status": "APPROVED", "reason": "Verification complete"},
            )
            assert resp.status_code == 200
            data = resp.json()["data"]
            assert data["kyc_status"] == "APPROVED"

            # 2. Check Audit Log
            audit_resp = await ac.get(
                "/api/v1/admin/audit-logs",
                headers={"Authorization": f"Bearer {ctx['token']}"},
            )
            assert audit_resp.status_code == 200
            logs = audit_resp.json()["data"]["data"]
            assert len(logs) >= 1
            assert logs[0]["action"] == "MERCHANT_STATUS_UPDATE"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_system_health(async_test_session, admin_auth):
    ctx = admin_auth

    async def override_db():
        yield async_test_session

    app.dependency_overrides[get_async_db_session] = override_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get(
                "/api/v1/admin/system/health",
                headers={"Authorization": f"Bearer {ctx['token']}"},
            )

        assert resp.status_code == 200
        res_json = resp.json()
        assert res_json["success"] is True
        data = res_json["data"]
        assert "components" in data
        assert any(c["name"] == "PostgreSQL" for c in data["components"])
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_unauthorized_access():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/v1/admin/merchants")
    assert resp.status_code == 401
