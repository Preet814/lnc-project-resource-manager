"""Screen 4.4 — Team timesheets (manager view)."""

from datetime import date

from prm.console.client import ApiError, PrmApiClient
from prm.console.screens.admin._helpers import read_int
from prm.console.screens.manager._helpers import read_week_start, timesheet_status_label
from prm.console.session import UserSession
from prm.console.ui import (
    clear_screen,
    pause,
    print_banner,
    print_divider,
    print_error,
    read_line,
)
from prm.console.ui.dates import format_date_input


def run(client: PrmApiClient, session: UserSession) -> None:
    week_start = read_week_start(
        "Filter by week (DD-MM-YYYY) or press Enter for current week:\nWeek: "
    )

    while True:
        clear_screen()
        print_banner("TIMESHEETS — MY TEAM")
        print(f"Week starting: {format_date_input(week_start)}")
        try:
            result = client.list_team_timesheets(
                session.access_token,
                week_start_date=week_start,
            )
        except ApiError as exc:
            print_error(str(exc))
            pause()
            return

        print()
        print_divider()
        print(f"{'Employee':<18}{'Project':<18}{'Hrs':<7}{'Status'}")
        print_divider()
        if result.rows:
            for row in result.rows:
                print(
                    f"{row.user_full_name:<18}{row.project_name:<18}"
                    f"{row.hours:<7}{timesheet_status_label(row.status)}"
                )
        else:
            print("(no timesheet rows for this week)")
        print_divider()
        print()
        print("[V] View employee timesheet detail     [B] Back")
        action = read_line("Enter action: ").strip().upper()
        if action in {"B", "BACK"}:
            return
        if action in {"V", "VIEW"}:
            _view_employee_detail(client, session, week_start)
            continue
        print_error("Enter V to view detail or B to go back.")
        pause()


def _view_employee_detail(
    client: PrmApiClient,
    session: UserSession,
    week_start: date,
) -> None:
    user_id = read_int("Enter Employee User ID: ")
    if user_id is None:
        pause()
        return

    try:
        detail = client.get_engineer_timesheet_detail(
            session.access_token,
            user_id,
            week_start_date=week_start,
        )
    except ApiError as exc:
        print_error(str(exc))
        pause()
        return

    clear_screen()
    print_banner("EMPLOYEE TIMESHEET DETAIL")
    print(f"── {detail.user_full_name} ─────────────────────────────────")
    print(f"Week Start : {format_date_input(detail.week_start_date)}")
    print(f"Status     : {timesheet_status_label(detail.status)}")
    print(f"Total Hours: {detail.total_hours}")
    print()
    if detail.entries:
        print(f"{'Project':<18}{'Hours':<8}{'Activity Tags'}")
        print_divider()
        for entry in detail.entries:
            tags = ", ".join(entry.activity_tags) if entry.activity_tags else "-"
            print(f"{entry.project_name:<18}{entry.hours_worked:<8}{tags}")
    else:
        print("No entries for this week.")
    print()
    print("[B] Back")
    read_line()
    pause()
