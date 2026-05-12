"""Uniform JSON response envelope, matching ai-backend's `{success, data, message}` shape."""
from typing import Any

from fastapi.responses import JSONResponse


def success_response(data: Any = None, message: str = "ok", status_code: int = 200) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"success": True, "data": data, "message": message})


def error_response(message: str, status_code: int = 400, code: str | None = None) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"success": False, "data": None, "message": message, "code": code})
