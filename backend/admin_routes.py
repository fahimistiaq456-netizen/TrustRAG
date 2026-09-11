"""Admin routes: audit log access and auth/RBAC self-check.

Endpoints (all ADMIN-only when auth is enabled):
    GET /audit                 - list recent runtime audit records
    GET /auth/status          - report whether auth is enabled + roles summary
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from .auth.dependencies import require_role
from .auth.models import RoleValue, User
from .config import get_settings

router = APIRouter()

LOGS_DIR = Path("logs")


class AuditQuery(BaseModel):
    limit: int = 200


@router.get("/audit")
def list_audit_events(query: AuditQuery | None = None, _: User = Depends(require_role("ADMIN"))) -> dict[str, object]:
    """Return the most recent audit log records (answer_*.json)."""
    limit = (query.limit if query else 200) or 200
    records: list[dict] = []
    if LOGS_DIR.exists():
        files = sorted(LOGS_DIR.glob("answer_*.json"), reverse=True)[:limit]
        for f in files:
            try:
                records.append(json.loads(f.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                continue
    return {"count": len(records), "records": records, "log_dir": str(LOGS_DIR)}


@router.get("/auth/status")
def auth_status(_: User = Depends(require_role("ADMIN"))) -> dict[str, object]:
    return {
        "auth_enabled": get_settings().auth_enabled,
        "roles": ["ADMIN", "EVALUATOR", "USER"],
    }