"""Shared helpers for admin console screens."""

from __future__ import annotations

from prm.console.client import ApiError, PrmApiClient
from prm.console.client.models import UserSummary
from prm.console.session import UserSession
from prm.console.ui import print_error, read_line, read_yes_no
from prm.domain.enums import Role


def role_label(role: Role) -> str:
    if role == Role.ENGINEER:
        return "ENGINEER"
    return role.value


def resolve_user(
    client: PrmApiClient,
    session: UserSession,
    identifier: str,
) -> UserSummary | None:
    stripped = identifier.strip()
    if not stripped:
        return None
    users = client.list_users(session.access_token)
    if stripped.isdigit():
        user_id = int(stripped)
        for user in users.users:
            if user.id == user_id:
                return user
        return None
    lowered = stripped.lower()
    for user in users.users:
        if user.username.lower() == lowered:
            return user
    return None


def read_user_identifier() -> str:
    return read_line("Enter Username or User ID: ")


def confirm_action(prompt: str) -> bool:
    print(prompt)
    print("[Y] Yes     [B] Cancel")
    result = read_yes_no("Your choice: ")
    return result is True


def read_int(prompt: str) -> int | None:
    value = read_line(prompt).strip()
    if not value:
        return None
    if not value.isdigit():
        print_error("Please enter a valid numeric ID.")
        return None
    return int(value)


def read_optional_line(prompt: str, current: str) -> str | None:
    value = read_line(f"{prompt} [{current}]: ")
    if not value:
        return None
    return value


def run_api_action(action: str, callback) -> bool:
    """Run callback; return True on success."""
    try:
        callback()
    except ApiError as exc:
        print_error(str(exc))
        return False
    return True
