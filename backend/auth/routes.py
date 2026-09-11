"""Authentication routes: register, login, me, and user management (ADMIN).

Endpoints:
    POST /auth/register   - create a USER account
    POST /auth/login      - exchange credentials for a JWT
    GET  /auth/me         - current user
    GET  /users           - list users (ADMIN)
    POST /users           - create user with a role (ADMIN)
    PATCH /users/{id}/role- change a user's role (ADMIN)
    DELETE /users/{id}    - remove a user (ADMIN)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..config import get_settings
from . import database
from .dependencies import get_current_user, require_role
from .models import RoleValue, User
from .security import create_access_token, verify_password

router = APIRouter()


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)


class LoginRequest(BaseModel):
    username: str
    password: str


class UserCreateRequest(RegisterRequest):
    role: RoleValue = "USER"


class RoleUpdateRequest(BaseModel):
    role: RoleValue


@router.post("/auth/register")
def register(req: RegisterRequest) -> dict[str, object]:
    require_open_registration()
    try:
        user = database.create_user(req.username, req.password, "USER")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"user": user.to_public()}


@router.post("/auth/login")
def login(req: LoginRequest) -> dict[str, object]:
    user = database.get_user_by_username(req.username)
    if user is None or user.disabled or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_access_token(user.id or 0, user.role)
    return {"access_token": token, "token_type": "bearer", "user": user.to_public()}


@router.get("/auth/me")
def me(user: User = Depends(get_current_user)) -> dict[str, object]:
    return {"user": user.to_public(), "auth_enabled": get_settings().auth_enabled}


@router.get("/users")
def users_list(_: User = Depends(require_role("ADMIN"))) -> dict[str, object]:
    return {"users": [u.to_public() for u in database.list_users()]}


@router.post("/users")
def users_create(req: UserCreateRequest, _: User = Depends(require_role("ADMIN"))) -> dict[str, object]:
    try:
        user = database.create_user(req.username, req.password, req.role)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"user": user.to_public()}


@router.patch("/users/{user_id}/role")
def users_update_role(user_id: int, req: RoleUpdateRequest, _: User = Depends(require_role("ADMIN"))) -> dict[str, object]:
    user = database.get_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    database.update_role(user_id, req.role)
    return {"user": database.get_user(user_id).to_public()}


@router.delete("/users/{user_id}")
def users_delete(user_id: int, current: User = Depends(require_role("ADMIN"))) -> dict[str, object]:
    user = database.get_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if current.id is not None and user_id == current.id:
        raise HTTPException(status_code=400, detail="Admins cannot delete their own account")
    database.delete_user(user_id)
    return {"deleted": user_id}


def require_open_registration() -> None:
    """Registration is open in development; enforce a policy flag if desired."""
    return None