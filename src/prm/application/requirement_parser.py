"""Parse part-time hour requests from manager natural-language input."""

import re

_HOURS_PER_WEEK_PATTERNS = (
    re.compile(
        r"(\d+)\s*(?:hrs?|hours?)\s*(?:/|\s*(?:per|a)\s*)?\s*week",
        re.IGNORECASE,
    ),
    re.compile(
        r"(\d+)\s*(?:hrs?|hours?)\s*(?:/|\s*(?:per|a)\s*)?\s*wk",
        re.IGNORECASE,
    ),
)


def parse_requested_hours_per_week(requirement: str) -> int | None:
    """Return requested weekly hours when stated; otherwise None for full-time requests."""
    for pattern in _HOURS_PER_WEEK_PATTERNS:
        match = pattern.search(requirement)
        if match:
            hours = int(match.group(1))
            if hours > 0:
                return hours
    return None
