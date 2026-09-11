"""SQLite-backed user store for the auth/RBAC system.

A single local database (``data/hallufix.db`` by default) keeps things simple
and fully local — no PostgreSQL is introduced.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from ..config import get_settings
from .models import RoleValue, User
from .security import hash_password

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'USER',
    disabled INTEGER NOT NULL DEFAULT 0
);
"""


def _db_path() -> Path:
    return Path(get_settings().db_path)


def get_connection() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute(_SCHEMA)
    conn.commit()
    return conn


def init_db() -> None:
    """Create tables and seed a default admin when the DB is empty."""
    conn = get_connection()
    try:
        count = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
        if count == 0:
            # Default admin; change the password after first login.
            conn.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                ("admin", hash_password("admin123"), "ADMIN"),
            )
            conn.commit()
    finally:
        conn.close()


def create_user(username: str, password: str, role: RoleValue = "USER") -> User:
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (username, hash_password(password), role),
        )
        conn.commit()
        return get_user(cur.lastrowid)  # type: ignore[arg-type]
    except sqlite3.IntegrityError as exc:
        raise ValueError(f"Username already exists: {username}") from exc
    finally:
        conn.close()


def get_user(user_id: int) -> User | None:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return _row_to_user(row)
    finally:
        conn.close()


def get_user_by_username(username: str) -> User | None:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return _row_to_user(row)
    finally:
        conn.close()


def list_users() -> list[User]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM users ORDER BY id").fetchall()
        return [u for u in (_row_to_user(r) for r in rows) if u is not None]
    finally:
        conn.close()


def update_role(user_id: int, role: RoleValue) -> None:
    conn = get_connection()
    try:
        conn.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
        conn.commit()
    finally:
        conn.close()


def delete_user(user_id: int) -> None:
    conn = get_connection()
    try:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()


def _row_to_user(row) -> User | None:
    if row is None:
        return None
    return User(
        id=int(row["id"]),
        username=row["username"],
        password_hash=row["password_hash"],
        role=row["role"],
        disabled=bool(row["disabled"]),
    )