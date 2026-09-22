from datetime import datetime, timedelta, timezone
import hashlib
import os
import secrets
from typing import Any

import jwt

from app.core.config import settings


def hash_password(password: str) -> str:
    """Hash a plaintext password using PBKDF2-HMAC-SHA256 with a random salt."""
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, 100_000
    )
    return f"{salt.hex()}:{key.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plaintext password against a stored PBKDF2 hash."""
    try:
        salt_hex, key_hex = password_hash.split(":")
        salt = bytes.fromhex(salt_hex)
        key = bytes.fromhex(key_hex)
        new_key = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, 100_000
        )
        return new_key == key
    except Exception:
        return False


def generate_api_key_pair(environment: str) -> tuple[str, str, str]:
    """
    Generate key_id, plaintext key_secret, and key_secret_hash.

    Prefixes key_id with rzp_test_ or rzp_live_ based on environment.
    """
    env_prefix = "rzp_test_" if environment.upper() == "TEST" else "rzp_live_"
    key_id = f"{env_prefix}{secrets.token_hex(5)}"
    key_secret = f"sec_{secrets.token_hex(10)}"
    key_secret_hash = hashlib.sha256(key_secret.encode("utf-8")).hexdigest()
    return key_id, key_secret, key_secret_hash


def create_access_token(
    subject: str | Any,
    expires_delta: timedelta | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """
    Generate a JWT access token.

    :param subject: Identity payload (e.g. user_id or email) stored under 'sub'.
    :param expires_delta: Optional custom duration for token validity.
    :param extra_claims: Optional dictionary of additional claims.
    :return: Encoded JWT access token string.
    """
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.access_token_expire_minutes)

    to_encode: dict[str, Any] = {
        "sub": str(subject),
        "iat": now,
        "exp": expire,
        "type": "access",
    }
    if extra_claims:
        to_encode.update(extra_claims)

    return jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def create_refresh_token(
    subject: str | Any,
    expires_delta: timedelta | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """
    Generate a JWT refresh token.

    :param subject: Identity payload (e.g. user_id or email) stored under 'sub'.
    :param expires_delta: Optional custom duration for token validity.
    :param extra_claims: Optional dictionary of additional claims.
    :return: Encoded JWT refresh token string.
    """
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(days=settings.refresh_token_expire_days)

    to_encode: dict[str, Any] = {
        "sub": str(subject),
        "iat": now,
        "exp": expire,
        "type": "refresh",
    }
    if extra_claims:
        to_encode.update(extra_claims)

    return jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_jwt(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT token using configured secret key and algorithm.

    :param token: Encoded JWT token string.
    :return: Decoded token claims dictionary.
    :raises jwt.PyJWTError: If token is invalid, expired, or malformed.
    """
    return jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )


def decode_access_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT access token, verifying type is 'access'.

    :param token: Encoded JWT access token string.
    :return: Decoded token claims dictionary.
    :raises jwt.PyJWTError: If token signature is invalid, expired, or malformed.
    :raises ValueError: If token type is not 'access'.
    """
    payload = decode_jwt(token)
    token_type = payload.get("type")
    if token_type and token_type != "access":
        raise ValueError("Invalid token type: expected access token")
    return payload

