"""FastAPI dependencies for authentication and role-based access control.

Use ``require_role("ADMIN")`` as a dependency on sensitive endpoints. When
auth is disabled (development mode), the dependency simply passes a synthetic
ADMIN user so existing local behaviour is preserved.
"""
from __future__ import annotations

from typing import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..config import get_settings
from . import database
from .models import RoleValue, User, has_role
from .security import decode_access_token

_bearer = HTTPBearer(auto_error=False)


def _disabled_user() -> User:
    return User(id=None, username="local", password_hash="", role="ADMIN")


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> User:
    """Resolve the JWT to a user; when auth is disabled, return a local admin."""
    if not get_settings().auth_enabled:
        return _disabled_user()
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload.get("sub"))
    except (ValueError, TypeError, KeyError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    user = database.get_user(user_id)
    if user is None or user.disabled:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or disabled")
    return user


def require_role(minimum: RoleValue) -> Callable:
    """Build a FastAPI dependency that enforces a minimum role."""

    def dependency(user: User = Depends(get_current_user)) -> User:
        if not has_role(user, minimum):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user

    return dependency