"""Screen 4.3 — My projects."""

from prm.console.client import ApiError, PrmApiClient
from prm.console.screens.manager._helpers import (
    health_label,
    load_manager_projects,
    select_project_by_number,
)
from prm.console.session import UserSession
from prm.console.ui import (
    clear_screen,
    pause,
    print_banner,
    print_divider,
    print_error,
    read_line,
)
from prm.console.ui.dates import format_date


def run(client: PrmApiClient, session: UserSession) -> None:
    while True:
        clear_screen()
        print_banner("MY PROJECTS")
        projects = load_manager_projects(client, session)
        if projects is None:
            pause()
            return
        if not projects:
            print("No projects assigned to you.")
            pause()
            return

        print(f"{'#':<4}{'Project':<18}{'End Date':<12}{'Health'}")
        print_divider(52)
        for index, project in enumerate(projects, start=1):
            print(
                f"{index:<4}{project.name:<18}"
                f"{format_date(project.end_date):<12}{health_label(project.health_status)}"
            )
        print_divider(52)
        print()
        raw = read_line("Select project number to view details (or B to go back): ").strip()
        if raw.upper() in {"B", "BACK"}:
            return
        if not raw.isdigit():
            print_error("Enter a project number or B.")
            pause()
            continue
        project = select_project_by_number(projects, int(raw))
        if project is None:
            print_error("Invalid project number.")
            pause()
            continue
        _show_project_detail(client, session, project.project_id)


def _show_project_detail(client: PrmApiClient, session: UserSession, project_id: int) -> None:
    try:
        detail = client.get_manager_project(session.access_token, project_id)
    except ApiError as exc:
        print_error(str(exc))
        pause()
        return

    while True:
        clear_screen()
        print_banner("PROJECT DETAIL")
        print(f"── {detail.name} ───────────────────────────────")
        print(f"Health Status : {health_label(detail.health_status)}")
        print()
        if detail.risk_flags:
            print("Risk Flags:")
            for flag in detail.risk_flags:
                prefix = "✗" if flag.strip().startswith(("✗", "x", "X")) else "•"
                cleaned = flag.lstrip("✗xX ").strip()
                print(f"  {prefix}  {cleaned}")
        else:
            print("Risk Flags: (none)")
        print()
        print("Milestones:")
        print(f"  {'#':<4}{'Title':<18}{'Due Date':<12}{'Status'}")
        for milestone in detail.milestones:
            overdue = "  ⚠ OVERDUE" if milestone.is_overdue else ""
            print(
                f"  {milestone.sequence_order:<4}{milestone.title:<18}"
                f"{format_date(milestone.due_date):<12}{milestone.status.value}{overdue}"
            )
        print()
        print("Allocated Resources:")
        if detail.allocated_resources:
            print(f"  {'Name':<16}{'%':<6}{'From':<12}{'To'}")
            for resource in detail.allocated_resources:
                print(
                    f"  {resource.user_full_name:<16}{resource.utilisation_percent}%{'':<3}"
                    f"{format_date(resource.from_date):<12}{format_date(resource.to_date)}"
                )
        else:
            print("  (none)")
        print()
        print_divider()
        print("[A] Get AI Risk Summary     [B] Back")
        action = read_line("Enter action: ").strip().upper()
        if action in {"B", "BACK"}:
            return
        if action in {"A", "AI"}:
            _show_risk_summary(client, session, project_id, detail.name)
            continue
        print_error("Enter A for risk summary or B to go back.")
        pause()


def _show_risk_summary(
    client: PrmApiClient,
    session: UserSession,
    project_id: int,
    project_name: str,
) -> None:
    clear_screen()
    print_banner(f"AI RISK SUMMARY — {project_name}")
    print("Generating AI summary...")
    try:
        summary = client.get_risk_summary(session.access_token, project_id)
    except ApiError as exc:
        print_error(str(exc))
        pause()
        return

    print()
    print(f"\"{summary.summary}\"")
    print()
    print(f"  Note: {summary.disclaimer}")
    print()
    print("[B] Back")
    read_line()
    pause()
