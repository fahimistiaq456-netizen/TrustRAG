"""User model and role constants for the Hallufix RBAC system."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

RoleValue = Literal["ADMIN", "EVALUATOR", "USER"]

# Permission mapping used to decide endpoint access.
ROLE_LEVELS: dict[str, int] = {"USER": 1, "EVALUATOR": 2, "ADMIN": 3}


@dataclass(frozen=True)
class User:
    id: int | None
    username: str
    password_hash: str
    role: RoleValue = "USER"
    disabled: bool = False

    def to_public(self) -> dict[str, object]:
        """Serializable representation that never exposes the password hash."""
        return {"id": self.id, "username": self.username, "role": self.role, "disabled": self.disabled}


def has_role(user: User, minimum: RoleValue) -> bool:
    """True when the user's role is at least ``minimum`` in ROLE_LEVELS."""
    return ROLE_LEVELS.get(user.role, 0) >= ROLE_LEVELS.get(minimum, 0)