"""Screen 4.1 — Resource dashboard."""

from prm.console.client import ApiError, PrmApiClient
from prm.console.screens.manager._helpers import availability_label, current_month_label
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
        print_banner(f"RESOURCE DASHBOARD — {current_month_label()}")
        try:
            dashboard = client.get_resource_dashboard(session.access_token)
        except ApiError as exc:
            print_error(str(exc))
            pause()
            return

        print(f"ON BENCH  ({dashboard.bench_count} employees available)")
        print_divider()
        print(f"{'ID':<5}{'Name':<18}{'Department':<14}{'Skills'}")
        for engineer in dashboard.on_bench:
            skills = ", ".join(engineer.skill_names) if engineer.skill_names else "-"
            print(f"{engineer.user_id:<5}{engineer.full_name:<18}{engineer.department:<14}{skills}")

        print()
        print("ACTIVE EMPLOYEES")
        print_divider()
        print(f"{'ID':<5}{'Name':<18}{'Alloc %':<10}{'Availability'}")
        for engineer in dashboard.active:
            availability = availability_label(
                engineer.utilisation_percent,
                engineer.availability_percent,
            )
            print(
                f"{engineer.user_id:<5}{engineer.full_name:<18}"
                f"{engineer.utilisation_percent}%{'':<6}{availability}"
            )

        print()
        print_divider()
        print(f"Bench: {dashboard.bench_count}   |   Partial: {dashboard.partial_count}")
        print()
        print("[D] Drill into employee details     [B] Back")
        action = read_line("Enter action: ").strip().upper()
        if action in {"B", "BACK"}:
            return
        if action in {"D", "DRILL"}:
            _show_engineer_detail(client, session)
            continue
        print_error("Enter D to drill in or B to go back.")
        pause()


def _show_engineer_detail(client: PrmApiClient, session: UserSession) -> None:
    raw = read_line("Enter Employee ID: ").strip()
    if not raw.isdigit():
        print_error("Please enter a valid employee ID.")
        pause()
        return

    try:
        detail = client.get_engineer_resource_detail(session.access_token, int(raw))
    except ApiError as exc:
        print_error(str(exc))
        pause()
        return

    clear_screen()
    print_banner("EMPLOYEE DETAIL")
    print(f"── {detail.full_name} ─────────────────────────────────")
    print(f"Department     : {detail.department}")
    print(
        f"Current Status : {detail.work_status.value} "
        f"({detail.current_utilisation_percent}%)"
    )
    skills = ", ".join(detail.profile_skills) if detail.profile_skills else "(none)"
    print(f"Profile Skills : {skills}")
    print()
    print("Active Allocations:")
    if detail.active_allocations:
        print(f"  {'Project':<16}{'%':<6}{'From':<12}{'To'}")
        for allocation in detail.active_allocations:
            print(
                f"  {allocation.project_name:<16}{allocation.utilisation_percent}%{'':<3}"
                f"{format_date(allocation.from_date):<12}{format_date(allocation.to_date)}"
            )
    else:
        print("  (none)")
    print()
    if detail.recent_activity_tags:
        print("Recent Activity Tags (last 4 weeks):")
        print(f"  {', '.join(detail.recent_activity_tags)}")
    print()
    print("[B] Back")
    read_line()
    pause()
