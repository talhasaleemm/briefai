"""
FastAPI dependency injection utilities — handles JWT authentication verification.
"""
from __future__ import annotations

import logging
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from briefai.internal.db import get_db
from briefai.utils.security import decode_token
from briefai.models import User

logger = logging.getLogger(__name__)

# Security scheme for JWT token headers (expects: Authorization: Bearer <token>)
reusable_oauth2 = HTTPBearer(auto_error=False)


def get_current_user(
    db: Session = Depends(get_db),
    token_cred: HTTPAuthorizationCredentials = Depends(reusable_oauth2),
) -> User:
    """
    Validates the JWT access token and yields the current authenticated User.
    Enforces correct token type and raises 401 on failure.
    """
    if not token_cred:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = token_cred.credentials
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user_id = int(payload["sub"])
    except Exception as exc:
        logger.warning("Token verification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user
