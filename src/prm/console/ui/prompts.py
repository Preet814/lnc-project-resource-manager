"""User input helpers for console screens."""

from __future__ import annotations

import getpass


def read_line(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        raise SystemExit(0) from None


def read_password(prompt: str) -> str:
    try:
        return getpass.getpass(prompt)
    except (EOFError, KeyboardInterrupt):
        print()
        raise SystemExit(0) from None


def read_option(prompt: str = "Enter option: ") -> str:
    return read_line(prompt)


def read_yes_no(prompt: str) -> bool | None:
    """Return True/False for Y/N, or None when user cancels with B."""
    value = read_line(prompt).strip().upper()
    if value in {"B", "BACK"}:
        return None
    if value in {"Y", "YES"}:
        return True
    if value in {"N", "NO"}:
        return False
    print("Please enter Y, N, or B.")
    return read_yes_no(prompt)


def read_save_or_back(prompt: str = "Enter action [S] Save / [B] Back: ") -> str | None:
    value = read_line(prompt).strip().upper()
    if value in {"S", "SAVE"}:
        return "save"
    if value in {"B", "BACK"}:
        return None
    print("Please enter S to save or B to go back.")
    return read_save_or_back(prompt)
