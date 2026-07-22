"""Cookie-session auth for /admin. Stdlib HMAC tokens — no extra deps."""

import hashlib
import hmac
import secrets
import time

from fastapi import Request
from fastapi.responses import RedirectResponse

from . import settings


def _sign(payload: str) -> str:
    mac = hmac.new(settings.SECRET_KEY.encode(), payload.encode(), hashlib.sha256)
    return mac.hexdigest()


def make_token() -> str:
    payload = f"{int(time.time())}.{secrets.token_hex(8)}"
    return f"{payload}.{_sign(payload)}"


def verify_token(token: str) -> bool:
    if not settings.auth_configured() or not token:
        return False
    parts = token.rsplit(".", 1)
    if len(parts) != 2:
        return False
    payload, sig = parts
    if not hmac.compare_digest(sig, _sign(payload)):
        return False
    try:
        issued = int(payload.split(".", 1)[0])
    except ValueError:
        return False
    return (time.time() - issued) < settings.SESSION_MAX_AGE


def check_password(password: str) -> bool:
    if not settings.auth_configured():
        return False
    return secrets.compare_digest(password, settings.ADMIN_PASSWORD)


def is_logged_in(request: Request) -> bool:
    return verify_token(request.cookies.get(settings.SESSION_COOKIE, ""))


def require_admin(request: Request):
    """Route dependency: redirect to login when the session is missing/expired."""
    if not is_logged_in(request):
        # FastAPI treats returning a response from a dependency as a normal
        # value, so raise via exception handler pattern instead.
        from fastapi import HTTPException

        raise HTTPException(status_code=303, headers={"Location": "/admin/login"})
