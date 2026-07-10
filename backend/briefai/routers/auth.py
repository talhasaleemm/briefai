"""
Authentication API router — handles registration, login, token refresh, and logout.
Encodes tokens, manages refresh token HTTP-only cookies, and enforces rate limits.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from briefai.internal.db import get_db
from briefai.utils.limiter import limiter
from briefai.utils.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from briefai.utils.deps import get_current_user
from briefai.config import settings
from briefai.models import User
from briefai.schemas import UserRegister, UserLogin, UserOut, Token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
@limiter.limit("3/30minutes")
async def register(
    request: Request,
    payload: UserRegister,
    db: Session = Depends(get_db),
) -> User:
    """Create a new user account with hashed password and unique constraints check."""
    # Check if email already registered
    if db.query(User).filter(User.email == payload.email.lower().strip()).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email address already registered.",
        )

    # Check if username already registered
    if db.query(User).filter(User.username == payload.username.lower().strip()).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken.",
        )

    new_user = User(
        email=payload.email.lower().strip(),
        username=payload.username.lower().strip(),
        hashed_password=hash_password(payload.password),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    logger.info("New user registered: %s", new_user.username)
    return new_user


@router.post(
    "/login",
    response_model=Token,
    summary="Authenticate user and issue tokens",
)
@limiter.limit("5/5minutes")
async def login(
    request: Request,
    response: Response,
    payload: UserLogin,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Validate credentials, set secure HTTP-only refresh token, and return access token."""
    login_str = payload.username_or_email.lower().strip()
    
    # Resolve user by username or email
    user = db.query(User).filter(
        (User.email == login_str) | (User.username == login_str)
    ).first()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username/email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Generate tokens
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    # Set refresh token in HttpOnly cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=not settings.DEBUG,  # True in production (HTTPS); False only in dev
        samesite="lax",  # CSRF protection
        max_age=7 * 24 * 60 * 60,  # 7 days in seconds
    )

    logger.info("User logged in: %s", user.username)
    return {"access_token": access_token, "token_type": "bearer"}


@router.post(
    "/refresh",
    response_model=Token,
    summary="Refresh access token using cookie",
)
async def refresh_token(
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Exchange a valid HTTP-only refresh token cookie for a new access token."""
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing.",
        )

    try:
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type.",
            )
        user_id = int(payload["sub"])
    except Exception as exc:
        logger.warning("Token refresh validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token.",
        ) from exc

    # Confirm user still exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists.",
        )

    new_access_token = create_access_token(user.id)
    return {"access_token": new_access_token, "token_type": "bearer"}


@router.post(
    "/logout",
    summary="Invalidate session and clear cookies",
)
async def logout(response: Response) -> dict[str, str]:
    """Clear secure refresh token cookie to log out user."""
    response.delete_cookie(key="refresh_token")
    return {"detail": "Successfully logged out."}


@router.get(
    "/me",
    response_model=UserOut,
    summary="Get current user profile",
)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user),
) -> User:
    """Return the profile info of the currently authenticated user."""
    return current_user

