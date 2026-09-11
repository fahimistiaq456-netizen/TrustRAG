"""Security primitives: password hashing and JWT-style access tokens.

Chosen to be dependency-free and reproducible on CPU-first Macs:

  * Password hashing uses PBKDF2-HMAC-SHA256 with a per-user random salt
    (``hashlib`` + ``secrets`` — no bcrypt/passlib needed).
  * Access tokens are compact, signed (HS256-style with HMAC-SHA256) JSON Web
    Tokens. We implement the compact JWT serialization ourselves so there is no
    hard requirement on a third-party JWT package.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

from ..config import get_settings

_ITERATIONS = 200_000
_ALGO = "HS256"


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------
def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), _ITERATIONS
    )
    return f"pbkdf2_sha256${_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt, digest_hex = stored.split("$")
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt), int(iterations)
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# Compact JWT helper (HS256)
# ---------------------------------------------------------------------------
def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _sign(signing_input: str, secret: str) -> str:
    """Sign a dot-separated JWT signing input with HMAC-SHA256."""
    sig = hmac.new(secret.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
    return _b64encode(sig)


def create_access_token(user_id: int, role: str, expires_minutes: int | None = None) -> str:
    settings = get_settings()
    minutes = expires_minutes or settings.access_token_expire_minutes
    now = int(time.time())
    header = _b64encode(json.dumps({"alg": _ALGO, "typ": "JWT"}).encode("utf-8"))
    payload = _b64encode(
        json.dumps({"sub": str(user_id), "role": role, "iat": now, "exp": now + minutes * 60}).encode("utf-8")
    )
    signing_input = f"{header}.{payload}"
    signature = _sign(signing_input, settings.jwt_secret)
    return f"{signing_input}.{signature}"


def decode_access_token(token: str) -> dict[str, Any]:
    """Validate signature + expiry; returns the payload or raises ValueError."""
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Malformed token.")
    header_b64, payload_b64, signature_b64 = parts
    signing_input = f"{header_b64}.{payload_b64}"
    expected = _sign(signing_input, get_settings().jwt_secret)
    if not hmac.compare_digest(signature_b64, expected):
        raise ValueError("Bad signature.")
    payload = json.loads(_b64decode(payload_b64).decode("utf-8"))
    if int(payload.get("exp", 0)) < int(time.time()):
        raise ValueError("Token expired.")
    return payload