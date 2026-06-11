"""Screen 3.3 — View all allocations (admin)."""

from prm.console.client import ApiError, PrmApiClient
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
    user_id: int | None = None
    project_id: int | None = None

    while True:
        clear_screen()
        print_banner("ALL ALLOCATIONS")
        try:
            result = client.list_allocations(
                session.access_token,
                user_id=user_id,
                project_id=project_id,
            )
        except ApiError as exc:
            print_error(str(exc))
            pause()
            return

        print(f"{'Employee':<18}{'Project':<18}{'%':<7}{'From':<12}{'To'}")
        print_divider(68)
        for allocation in result.allocations:
            end = format_date(allocation.to_date)
            print(
                f"{allocation.user_full_name:<18}{allocation.project_name:<18}"
                f"{allocation.utilisation_percent}%{'':<4}"
                f"{format_date(allocation.from_date):<12}{end}"
            )
        print_divider(68)
        print(f"Total Active Allocations: {result.total}")
        if user_id or project_id:
            parts = []
            if user_id:
                parts.append(f"employee_id={user_id}")
            if project_id:
                parts.append(f"project_id={project_id}")
            print(f"Filters: {', '.join(parts)}")
        print()
        print("[F] Filter by Employee / Project     [B] Back")
        action = read_line("Enter action: ").strip().upper()
        if action in {"B", "BACK"}:
            return
        if action in {"F", "FILTER"}:
            user_id, project_id = _read_allocation_filters()
            continue
        print_error("Enter F to filter or B to go back.")
        pause()


def _read_allocation_filters() -> tuple[int | None, int | None]:
    clear_screen()
    print_banner("FILTER ALLOCATIONS")
    user_raw = read_line("Employee User ID (blank = any): ").strip()
    project_raw = read_line("Project ID (blank = any): ").strip()
    user_id = int(user_raw) if user_raw.isdigit() else None
    project_id = int(project_raw) if project_raw.isdigit() else None
    return user_id, project_id
