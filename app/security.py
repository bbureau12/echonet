from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from .settings import settings


def require_api_key(request: Request) -> JSONResponse | None:
    # allow liveness
    if request.url.path == "/health":
        return None

    got = (request.headers.get("X-API-Key") or "").strip()
    if not got or got != settings.api_key:
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    return None


def require_admin_key(request: Request) -> JSONResponse | None:
    # Only for /register if admin_key is configured
    if not settings.admin_key:
        return None

    got = (request.headers.get("X-Admin-Key") or "").strip()
    if not got or got != settings.admin_key:
        return JSONResponse(status_code=401, content={"detail": "Admin key required"})
    return None
