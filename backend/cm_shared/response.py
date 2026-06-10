"""Uniform JSON response envelope, matching ai-backend's `{success, data, message}` shape."""
from typing import Any

from fastapi.responses import JSONResponse


def success_response(data: Any = None, message: str = "ok", status_code: int = 200) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"success": True, "data": data, "message": message})


def error_response(message: str, status_code: int = 400, code: str | None = None) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"success": False, "data": None, "message": message, "code": code})


def unwrap_response(resp: Any) -> Any:
    """Inverse of `success_response`: pull `data` out of a `{success, data, message}`
    envelope, or pass through anything that isn't one. Used by service-to-service
    callers (agent-service tools) that receive an already-decoded envelope."""
    if isinstance(resp, dict) and "data" in resp and "success" in resp:
        return resp.get("data")
    return resp
