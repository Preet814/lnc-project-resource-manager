"""Date parsing and formatting for console prompts (BRD DD-MM-YYYY)."""

from datetime import date, datetime


def format_date(value: date | datetime | None) -> str:
    if value is None:
        return "-"
    if isinstance(value, datetime):
        value = value.date()
    return value.strftime("%d-%b-%y")


def format_date_input(value: date | None) -> str:
    if value is None:
        return ""
    return value.strftime("%d-%m-%Y")


def parse_date(value: str) -> date | None:
    stripped = value.strip()
    if not stripped:
        return None
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(stripped, fmt).date()
        except ValueError:
            continue
    return None
