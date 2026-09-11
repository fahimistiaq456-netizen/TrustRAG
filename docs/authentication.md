# Authentication & RBAC

## What it does
Adds optional authentication and role-based access control (RBAC) without complicating
local development. When `HALLUFIX_AUTH_ENABLED=false` (the default) every existing
endpoint is open and behaves exactly as before; when enabled, sensitive endpoints are
protected and roles are enforced.

## Why it exists
Enterprise "access control" is one of the audited missing features. A lightweight,
fully-local JWT + SQLite implementation delivers the academic/enterprise story (roles,
hashed passwords, token expiry, no privilege escalation) without dragging in PostgreSQL
or a cloud identity provider.

## Roles
| Role | Permissions |
|---|---|
| `USER` | ask questions, view answers, view permitted sources |
| `EVALUATOR` | everything `USER` can do + evaluation tools, submit human evaluations, view results |
| `ADMIN` | everything + ingest documents, manage users, view audit logs, system config |

## Architecture (`backend/auth/`)
- `models.py` — `User` dataclass, `RoleValue`, `ROLE_LEVELS`, `has_role`. `to_public()`
  **never** exposes the password hash.
- `security.py` — PBKDF2 password hashing (`hash_password` / `verify_password`) and JWT
  creation/decoding (`create_access_token` / `decode_access_token`) with expiry.
- `database.py` — SQLite user store (default `data/hallufix.db`); seeds a default
  `admin / admin123` when empty. Uniqueness on username.
- `dependencies.py` — `get_current_user` (resolves JWT; when auth disabled returns a
  local admin so dev keeps working) and `require_role(minimum)` (403 if role too low).
- `routes.py` — `POST /auth/register`, `POST /auth/login`, `GET /auth/me`,
  `GET /users`, `POST /users`, `PATCH /users/{id}/role`, `DELETE /users/{id}`.
- Protected endpoints: `POST /ingest` and `GET /audit` are ADMIN-only, evaluation routes
  are EVALUATOR+, `/users` management is ADMIN-only.

## Configuration (`backend/config.py`, `.env`)
| Variable | Default | Meaning |
|---|---|---|
| `HALLUFIX_AUTH_ENABLED` | `false` | Turn RBAC on/off |
| `HALLUFIX_JWT_SECRET` | `change-me-in-production` | **Override with a long random value** when enabling auth |
| `HALLUFIX_ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | JWT lifetime |
| `HALLUFIX_DB_PATH` | `data/hallufix.db` | SQLite user database |

Secrets are never logged; `to_public()` strips hashes; `.env` is git-ignored.

## How to run / test
```bash
pytest tests/test_auth.py
```
Tests cover password round-trip, register→login→me, invalid password rejection, expired
and tampered tokens, USER-forbidden on admin endpoints, ADMIN access, and privilege
escalation blocking. `data/hallufix.db` is created/checked at startup; generate a strong
secret with `python -c "import secrets; print(secrets.token_hex(32))"`.

## Limitations
- Single-node local SQLite — fine for a university project; not a distributed directory.
- The default `admin/admin123` must be changed in any non-demo deployment.
- When `HALLUFIX_AUTH_ENABLED=false`, `/auth/me` and role dependencies resolve to the
  local dev admin, which is the intended dev-mode behaviour.