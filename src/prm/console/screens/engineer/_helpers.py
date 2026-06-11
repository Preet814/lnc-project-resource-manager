"""Shared helpers for engineer console screens."""

from datetime import date, timedelta

from prm.console.client.models import MyTimesheetWeekSummary
from prm.domain.enums import ActivityTag, TimesheetWeekStatus
from prm.domain.week_calendar import week_start_on_or_before

ACTIVITY_TAG_CHOICES: dict[str, ActivityTag] = {
    "1": ActivityTag.BACKEND_API,
    "2": ActivityTag.MICROSERVICES,
    "3": ActivityTag.DATABASE_DESIGN,
    "4": ActivityTag.WEBSOCKET,
    "5": ActivityTag.FRONTEND,
    "6": ActivityTag.CODE_REVIEW,
    "7": ActivityTag.BUG_FIXING,
    "8": ActivityTag.DEVOPS,
    "9": ActivityTag.TESTING_QA,
    "10": ActivityTag.DOCUMENTATION,
    "11": ActivityTag.OTHER,
}

ACTIVITY_TAG_LABELS: dict[str, str] = {
    "1": "Backend API Development",
    "2": "Microservices / Architecture",
    "3": "Database Design & Queries",
    "4": "WebSocket / Real-time Features",
    "5": "Frontend Development",
    "6": "Code Review / Mentoring",
    "7": "Bug Fixing",
    "8": "DevOps / Deployment",
    "9": "Testing & QA",
    "10": "Documentation",
    "11": "Other",
}


def default_week_start() -> date:
    return week_start_on_or_before(date.today())


def last_completed_week_start() -> date:
    return default_week_start() - timedelta(days=7)


def timesheet_reminder_week(
    weeks: tuple[MyTimesheetWeekSummary, ...],
) -> date | None:
    """Return week start if the most recent completed week lacks a SUBMITTED timesheet."""
    target = last_completed_week_start()
    for week in weeks:
        if week.week_start_date == target:
            if week.status == TimesheetWeekStatus.SUBMITTED:
                return None
            return target
    return target


def timesheet_status_label(status: TimesheetWeekStatus) -> str:
    if status == TimesheetWeekStatus.MISSED:
        return f"{status.value}    ⚠"
    return status.value


def format_activity_tags(tags: tuple[str, ...] | list[str]) -> str:
    if not tags:
        return "-"
    return ", ".join(tags)


def print_activity_tag_menu() -> None:
    print("What did you work on? Select activity tags:")
    print()
    for key, label in ACTIVITY_TAG_LABELS.items():
        print(f"  {key:>2}.  {label}")
    print()


def parse_activity_tags(raw: str) -> list[ActivityTag]:
    tags: list[ActivityTag] = []
    for part in raw.split(","):
        token = part.strip()
        if not token:
            continue
        if token in ACTIVITY_TAG_CHOICES:
            tag = ACTIVITY_TAG_CHOICES[token]
        else:
            try:
                tag = ActivityTag(token.upper().replace(" ", "_"))
            except ValueError:
                tag = ActivityTag.OTHER
        if tag not in tags:
            tags.append(tag)
    return tags
