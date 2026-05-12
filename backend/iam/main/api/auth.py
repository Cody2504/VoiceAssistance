from fastapi import APIRouter, Depends, HTTPException, status
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cm_shared.auth import decode_token, issue_access, issue_refresh
from cm_shared.db import get_session
from cm_shared.response import success_response
from cm_shared.schemas import LoginRequest, RefreshRequest, RegisterRequest, TokenPair, UserOut
from main.models.user import User

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


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
    if not user or not pwd.verify(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")

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

    tokens = TokenPair(
        access_token=issue_access(user.id, user.email, user.role),
        refresh_token=issue_refresh(user.id, user.email, user.role),
    )
    return success_response(tokens.model_dump())
