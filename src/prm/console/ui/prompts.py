"""User input helpers for console screens."""

from __future__ import annotations

import getpass
import sys

# Characters shown before masking the rest (passwords, API keys).
_PASSWORD_VISIBLE_PREFIX = 3


def read_line(prompt: str = "") -> str:
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        raise SystemExit(0) from None


def read_password(prompt: str, *, visible_prefix: int = _PASSWORD_VISIBLE_PREFIX) -> str:
    """Read a secret; show the first few characters, then mask with asterisks."""
    try:
        if not sys.stdin.isatty():
            return getpass.getpass(prompt)
        sys.stdout.write(prompt)
        sys.stdout.flush()
        if sys.platform == "win32":
            value = _read_masked_windows(visible_prefix)
        else:
            value = _read_masked_posix(visible_prefix)
        return value
    except (EOFError, KeyboardInterrupt):
        print()
        raise SystemExit(0) from None


def _echo_masked_char(char: str, index: int, visible_prefix: int) -> None:
    if index <= visible_prefix:
        sys.stdout.write(char)
    else:
        sys.stdout.write("*")
    sys.stdout.flush()


def _erase_last_masked_char() -> None:
    sys.stdout.write("\b \b")
    sys.stdout.flush()


def _read_masked_posix(visible_prefix: int) -> str:
    import termios
    import tty

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    chars: list[str] = []
    try:
        tty.setraw(fd)
        while True:
            ch = sys.stdin.read(1)
            if ch in ("\r", "\n"):
                sys.stdout.write("\n")
                break
            if ch in ("\x7f", "\x08"):
                if chars:
                    chars.pop()
                    _erase_last_masked_char()
                continue
            if ch == "\x03":
                raise KeyboardInterrupt
            if ch == "\x04":
                raise EOFError
            chars.append(ch)
            _echo_masked_char(ch, len(chars), visible_prefix)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return "".join(chars)


def _read_masked_windows(visible_prefix: int) -> str:
    import msvcrt

    chars: list[str] = []
    while True:
        ch = msvcrt.getwch()
        if ch in ("\r", "\n"):
            sys.stdout.write("\n")
            break
        if ch == "\x03":
            raise KeyboardInterrupt
        if ch in ("\x08", "\x7f"):
            if chars:
                chars.pop()
                _erase_last_masked_char()
            continue
        chars.append(ch)
        _echo_masked_char(ch, len(chars), visible_prefix)
    return "".join(chars)


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
