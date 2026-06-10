from fastapi import APIRouter, Depends, HTTPException, status
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cm_shared.auth import decode_token, issue_access, issue_refresh
from cm_shared.db import get_session
from cm_shared.response import success_response
from cm_shared.schemas import (
    GoogleAuthRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UserOut,
)
from main.google_oauth import verify_google_id_token
from main.models.user import User
from main.settings import get_settings

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _token_response(user: User) -> dict:
    """Issue a Jockey access/refresh pair for `user` and shape the response
    exactly like /login and /register so the frontend reuses one handler."""
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account suspended")
    tokens = TokenPair(
        access_token=issue_access(user.id, user.email, user.role),
        refresh_token=issue_refresh(user.id, user.email, user.role),
    )
    return success_response({
        "user": UserOut.model_validate(user, from_attributes=True).model_dump(mode="json"),
        "tokens": tokens.model_dump(),
    })


@router.post("/register")
async def register(body: RegisterRequest, session: AsyncSession = Depends(get_session)):
    existing = (await session.execute(select(User).where(User.email == body.email))).scalar_one_or_none()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    user = User(email=body.email, password_hash=pwd.hash(body.password), role="user")
    session.add(user)
    await session.commit()
    await session.refresh(user)

    tokens = TokenPair(
        access_token=issue_access(user.id, user.email, user.role),
        refresh_token=issue_refresh(user.id, user.email, user.role),
    )
    return success_response({"user": UserOut.model_validate(user, from_attributes=True).model_dump(mode="json"),
                             "tokens": tokens.model_dump()})


@router.post("/login")
async def login(body: LoginRequest, session: AsyncSession = Depends(get_session)):
    user = (await session.execute(select(User).where(User.email == body.email))).scalar_one_or_none()
    # password_hash is None for social-only (Google) accounts — reject cleanly.
    if not user or not user.password_hash or not pwd.verify(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account suspended")

    tokens = TokenPair(
        access_token=issue_access(user.id, user.email, user.role),
        refresh_token=issue_refresh(user.id, user.email, user.role),
    )
    return success_response({"user": UserOut.model_validate(user, from_attributes=True).model_dump(mode="json"),
                             "tokens": tokens.model_dump()})


@router.post("/renew")
async def renew(body: RefreshRequest, session: AsyncSession = Depends(get_session)):
    payload = decode_token(body.refresh_token, expected_type="refresh")
    user = await session.get(User, payload.sub)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User no longer exists")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account suspended")

    tokens = TokenPair(
        access_token=issue_access(user.id, user.email, user.role),
        refresh_token=issue_refresh(user.id, user.email, user.role),
    )
    return success_response(tokens.model_dump())


@router.post("/google")
async def google_auth(body: GoogleAuthRequest, session: AsyncSession = Depends(get_session)):
    settings = get_settings()
    if not settings.google_client_id:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Google sign-in is not configured")

    claims = await verify_google_id_token(body.credential, settings.google_client_id)
    if not claims.get("email_verified", False):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Google email is not verified")
    email = (claims.get("email") or "").lower()
    sub = claims.get("sub")
    if not email or not sub:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Google token missing email or subject")

    # 1) already linked by Google subject id
    user = (await session.execute(select(User).where(User.google_sub == sub))).scalar_one_or_none()
    if user is None:
        # 2) link to an existing account with this (verified) email, else 3) create one
        user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if user is None:
            user = User(email=email, password_hash=None, google_sub=sub, role="user")
            session.add(user)
        else:
            user.google_sub = sub
        await session.commit()
        await session.refresh(user)

    return _token_response(user)
