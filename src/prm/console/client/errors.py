"""HTTP client error types for the console."""

from __future__ import annotations

from typing import Any

import httpx


class ApiError(Exception):
    """Raised when the REST API returns a non-success response."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def parse_error_message(response: httpx.Response) -> str:
    try:
        body: dict[str, Any] = response.json()
    except ValueError:
        return f"Request failed with status {response.status_code}."

    detail = body.get("detail")
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list):
        parts: list[str] = []
        for item in detail:
            if isinstance(item, dict):
                loc = ".".join(str(part) for part in item.get("loc", ()))
                msg = item.get("msg", "Invalid value")
                parts.append(f"{loc}: {msg}" if loc else str(msg))
            else:
                parts.append(str(item))
        if parts:
            return "; ".join(parts)
    return f"Request failed with status {response.status_code}."
