"""Tests for Phase 6 — authentication and RBAC.

Uses an in-memory/temp SQLite DB and the FastAPI TestClient. When auth is
disabled (dev mode), endpoints are open; when enabled, JWT + role enforcement
must work, expired tokens must be rejected, and privilege escalation must be
blocked.
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.auth import database
from backend.auth.dependencies import get_current_user, require_role
from backend.auth.models import User
from backend.auth.security import create_access_token


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from backend.config import get_settings
    get_settings().db_path = str(tmp_path / "test.db")
    get_settings().auth_enabled = False
    database.init_db()
    from backend.api import app
    return TestClient(app)


@pytest.fixture()
def auth_client(tmp_path, monkeypatch):
    from backend.config import get_settings
    get_settings().db_path = str(tmp_path / "auth.db")
    get_settings().auth_enabled = True
    database.init_db()
    from backend.api import app
    return TestClient(app)


def test_password_hash_roundtrip():
    from backend.auth.security import hash_password, verify_password
    h = hash_password("correct horse")
    assert verify_password("correct horse", h)
    assert not verify_password("wrong", h)
    assert not verify_password("correct horse", "not-a-valid-format")


def test_register_login_me(auth_client):
    # Uses the auth-*enabled* fixture so /auth/me honours the JWT from /auth/login
    # (when auth is disabled the endpoint returns the local dev admin instead).
    r = auth_client.post("/auth/register", json={"username": "alice", "password": "secret1"})
    assert r.status_code == 200
    r = auth_client.post("/auth/login", json={"username": "alice", "password": "secret1"})
    assert r.status_code == 200
    token = r.json()["access_token"]
    me = auth_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["user"]["username"] == "alice"
    assert me.json()["user"]["role"] == "USER"


def test_login_invalid_password_rejected(client):
    client.post("/auth/register", json={"username": "carol", "password": "secret1"})
    r = client.post("/auth/login", json={"username": "carol", "password": "wrong!"})
    assert r.status_code == 401


def test_admin_required_endpoints_when_auth_enabled(auth_client):
    # no token -> 401/403 on sensitive endpoints
    assert auth_client.get("/users").status_code in (401, 403)
    assert auth_client.get("/audit").status_code in (401, 403)
    assert auth_client.post("/ingest", files=[]).status_code in (401, 403)


def test_user_cannot_access_admin_endpoints(auth_client):
    r = auth_client.post("/auth/register", json={"username": "user1", "password": "secret1"})
    token = auth_client.post("/auth/login", json={"username": "user1", "password": "secret1"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert auth_client.get("/users", headers=headers).status_code == 403
    assert auth_client.get("/audit", headers=headers).status_code == 403


def test_admin_can_access_admin_endpoints(auth_client):
    token = auth_client.post("/auth/login", json={"username": "admin", "password": "admin123"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert auth_client.get("/users", headers=headers).status_code == 200
    assert auth_client.get("/audit", headers=headers).status_code == 200


def test_expired_token_rejected(auth_client):
    from backend.config import get_settings
    token = create_access_token(1, "ADMIN", expires_minutes=-1)
    me = auth_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 401


def test_tampered_token_rejected(auth_client):
    token = auth_client.post("/auth/login", json={"username": "admin", "password": "admin123"}).json()["access_token"]
    tampered = token[:-2] + ("aa" if token[-2:] != "aa" else "bb")
    me = auth_client.get("/auth/me", headers={"Authorization": f"Bearer {tampered}"})
    assert me.status_code == 401


def test_privilege_escalation_blocked(auth_client):
    # A USER token cannot read user management endpoints.
    auth_client.post("/auth/register", json={"username": "eve", "password": "secret1"})
    token = auth_client.post("/auth/login", json={"username": "eve", "password": "secret1"}).json()["access_token"]
    r = auth_client.post("/users", json={"username": "root2", "password": "pass12", "role": "ADMIN"},
                         headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403