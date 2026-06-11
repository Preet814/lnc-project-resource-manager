"""Shared helpers for manager console screens."""

from __future__ import annotations

from datetime import date, datetime

from prm.console.client import ApiError, PrmApiClient
from prm.console.client.models import ManagerProjectSummary
from prm.console.session import UserSession
from prm.console.ui import print_error, read_line
from prm.console.ui.dates import parse_date
from prm.domain.enums import ProjectHealthStatus, TimesheetWeekStatus


def health_label(status: ProjectHealthStatus) -> str:
    labels = {
        ProjectHealthStatus.ON_TRACK: "🟢 ON TRACK",
        ProjectHealthStatus.ATTENTION: "🟡 ATTENTION",
        ProjectHealthStatus.AT_RISK: "🔴 AT RISK",
    }
    return labels.get(status, status.value)


def availability_label(utilisation_percent: int, availability_percent: int) -> str:
    if utilisation_percent >= 100:
        return "FULL"
    return f"{availability_percent}% free"


def timesheet_status_label(status: TimesheetWeekStatus) -> str:
    if status == TimesheetWeekStatus.MISSED:
        return f"{status.value} ⚠"
    return status.value


def current_month_label() -> str:
    return datetime.now().strftime("%b %Y")


def default_week_start() -> date:
    from datetime import timedelta

    today = date.today()
    return today - timedelta(days=today.weekday())


def read_week_start(prompt: str) -> date:
    raw = read_line(prompt).strip()
    if not raw:
        return default_week_start()
    parsed = parse_date(raw)
    if parsed is None:
        print_error("Invalid date. Using current week.")
        return default_week_start()
    return parsed


def load_manager_projects(
    client: PrmApiClient,
    session: UserSession,
) -> tuple[ManagerProjectSummary, ...] | None:
    try:
        return client.list_manager_projects(session.access_token).projects
    except ApiError as exc:
        print_error(str(exc))
        return None


def resolve_project(
    projects: tuple[ManagerProjectSummary, ...],
    identifier: str,
) -> ManagerProjectSummary | None:
    stripped = identifier.strip()
    if not stripped:
        return None
    if stripped.isdigit():
        project_id = int(stripped)
        for project in projects:
            if project.project_id == project_id:
                return project
        return None
    lowered = stripped.lower()
    for project in projects:
        if project.name.lower() == lowered:
            return project
    for project in projects:
        if lowered in project.name.lower():
            return project
    return None


def select_project(
    client: PrmApiClient,
    session: UserSession,
    *,
    prompt: str = "Enter project name or ID: ",
) -> ManagerProjectSummary | None:
    projects = load_manager_projects(client, session)
    if not projects:
        return None
    identifier = read_line(prompt).strip()
    project = resolve_project(projects, identifier)
    if project is None:
        print_error("Project not found or not assigned to you.")
    return project


def select_project_by_number(
    projects: tuple[ManagerProjectSummary, ...],
    number: int,
) -> ManagerProjectSummary | None:
    if number < 1 or number > len(projects):
        return None
    return projects[number - 1]
