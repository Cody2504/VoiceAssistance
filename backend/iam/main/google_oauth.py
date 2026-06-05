"""Verify Google Identity Services ID tokens against Google's public JWKS.

We verify the token server-side — RSA signature (Google's rotating keys) plus
audience / issuer / expiry — using the service's existing deps (httpx +
python-jose), so no extra package or image rebuild is required.
"""
import time

import httpx
from fastapi import HTTPException, status
from jose import jwt
from jose.exceptions import JWTError

_GOOGLE_CERTS_URL = "https://www.googleapis.com/oauth2/v3/certs"
_GOOGLE_ISSUERS = ("accounts.google.com", "https://accounts.google.com")
_JWKS_TTL_S = 3600

_jwks: dict | None = None
_jwks_fetched_at: float = 0.0


async def _fetch_jwks(force: bool = False) -> dict:
    global _jwks, _jwks_fetched_at
    now = time.time()
    if _jwks is not None and not force and now - _jwks_fetched_at < _JWKS_TTL_S:
        return _jwks
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.get(_GOOGLE_CERTS_URL)
        resp.raise_for_status()
        _jwks = resp.json()
        _jwks_fetched_at = now
    return _jwks


def _decode(token: str, jwks: dict, client_id: str) -> dict:
    return jwt.decode(
        token,
        jwks,
        algorithms=["RS256"],
        audience=client_id,
        issuer=_GOOGLE_ISSUERS,
    )


async def verify_google_id_token(token: str, client_id: str) -> dict:
    """Return the verified Google ID-token claims, or raise 401/503."""
    try:
        jwks = await _fetch_jwks()
        try:
            return _decode(token, jwks, client_id)
        except JWTError:
            # likely key rotation — refresh the JWKS once and retry
            jwks = await _fetch_jwks(force=True)
            return _decode(token, jwks, client_id)
    except JWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid Google token") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Could not reach Google") from exc
