"""
Security utility module — handles password hashing and JWT token operations.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt
from passlib.context import CryptContext

from app.core.config import settings

# Initialize CryptContext for bcrypt password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_token(
    subject: str | int,
    expires_delta: timedelta,
    token_type: str = "access",
) -> str:
    """
    Generate a signed JWT token containing subject, expiry, and token type.
    """
    now = datetime.now(timezone.utc)
    expire = now + expires_delta
    payload = {
        "sub": str(subject),
        "exp": expire,
        "iat": now,
        "nbf": now,
        "type": token_type,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(subject: str | int) -> str:
    """Create a short-lived access token."""
    expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return create_token(subject, expires, token_type="access")


def create_refresh_token(subject: str | int) -> str:
    """Create a long-lived refresh token."""
    expires = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return create_token(subject, expires, token_type="refresh")


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT token.
    Raises jwt.PyJWTError if the token is invalid or expired.
    """
    return jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
        options={"require": ["exp", "sub", "type"]},
    )
