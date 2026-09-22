from datetime import timedelta
import pytest
from fastapi import HTTPException, status
import jwt

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_jwt,
)
from app.dependencies import (
    RoleChecker,
    get_current_active_user,
    get_current_user,
)


def test_create_and_decode_access_token():
    user_id = "usr_12345"
    token = create_access_token(
        subject=user_id,
        extra_claims={"roles": ["admin"], "email": "test@example.com"},
    )
    assert isinstance(token, str)

    payload = decode_jwt(token)
    assert payload["sub"] == user_id
    assert payload["type"] == "access"
    assert payload["roles"] == ["admin"]
    assert payload["email"] == "test@example.com"
    assert "exp" in payload
    assert "iat" in payload


def test_create_and_decode_refresh_token():
    user_id = "usr_67890"
    token = create_refresh_token(subject=user_id)
    assert isinstance(token, str)

    payload = decode_jwt(token)
    assert payload["sub"] == user_id
    assert payload["type"] == "refresh"
    assert "exp" in payload


def test_decode_access_token_validation():
    user_id = "usr_access"
    access_token = create_access_token(subject=user_id)
    payload = decode_access_token(access_token)
    assert payload["sub"] == user_id

    refresh_token = create_refresh_token(subject=user_id)
    with pytest.raises(ValueError, match="Invalid token type"):
        decode_access_token(refresh_token)


def test_decode_expired_token():
    expired_token = create_access_token(
        subject="usr_expired",
        expires_delta=timedelta(seconds=-10),
    )
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_jwt(expired_token)


def test_decode_invalid_token():
    with pytest.raises(jwt.PyJWTError):
        decode_jwt("invalid.token.str")


@pytest.mark.asyncio
async def test_get_current_user_dependency_valid():
    user_id = "usr_valid"
    token = create_access_token(
        subject=user_id,
        extra_claims={"roles": ["merchant_admin"]},
    )

    user = await get_current_user(token=token, bearer_credentials=None)
    assert user["sub"] == user_id
    assert user["roles"] == ["merchant_admin"]


@pytest.mark.asyncio
async def test_get_current_user_dependency_missing():
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token=None, bearer_credentials=None)
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_get_current_user_dependency_invalid_type():
    refresh_token = create_refresh_token(subject="usr_refresh")
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token=refresh_token, bearer_credentials=None)
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_get_current_active_user_dependency():
    active_payload = {"sub": "usr_active", "disabled": False, "is_active": True}
    res = await get_current_active_user(current_user=active_payload)
    assert res == active_payload

    inactive_payload = {"sub": "usr_inactive", "disabled": True, "is_active": True}
    with pytest.raises(HTTPException) as exc_info:
        await get_current_active_user(current_user=inactive_payload)
    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST


def test_role_checker_dependency():
    checker = RoleChecker(allowed_roles=["admin", "merchant_owner"])

    valid_user = {"sub": "usr_admin", "roles": ["admin"]}
    assert checker(current_user=valid_user) == valid_user

    invalid_user = {"sub": "usr_user", "roles": ["regular_user"]}
    with pytest.raises(HTTPException) as exc_info:
        checker(current_user=invalid_user)
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
