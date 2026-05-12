"""JWT issuance, verification, and FastAPI dependency for protected routes."""
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from cm_shared.settings import BaseServiceSettings, get_base_settings


class TokenPayload(BaseModel):
    sub: str          # user id (UUID as str)
    email: str
    role: str
    type: str         # "access" | "refresh"
    exp: int


def _now_ts() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def _encode(payload: dict[str, Any], settings: BaseServiceSettings) -> str:
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def issue_access(user_id: UUID, email: str, role: str, settings: BaseServiceSettings | None = None) -> str:
    s = settings or get_base_settings()
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "type": "access",
        "exp": _now_ts() + s.access_token_ttl_min * 60,
    }
    return _encode(payload, s)


def issue_refresh(user_id: UUID, email: str, role: str, settings: BaseServiceSettings | None = None) -> str:
    s = settings or get_base_settings()
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "type": "refresh",
        "exp": _now_ts() + s.refresh_token_ttl_days * 86400,
    }
    return _encode(payload, s)


def decode_token(token: str, expected_type: str, settings: BaseServiceSettings | None = None) -> TokenPayload:
    s = settings or get_base_settings()
    try:
        raw = jwt.decode(token, s.secret_key, algorithms=[s.jwt_algorithm])
    except JWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token") from exc

    payload = TokenPayload(**raw)
    if payload.type != expected_type:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Expected {expected_type} token, got {payload.type}")
    return payload


_bearer = HTTPBearer(auto_error=True)


def require_user(creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> TokenPayload:
    """FastAPI dependency for protected routes. Returns the decoded access token payload."""
    return decode_token(creds.credentials, expected_type="access")


def require_admin(payload: TokenPayload = Depends(require_user)) -> TokenPayload:
    if payload.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin role required")
    return payload
