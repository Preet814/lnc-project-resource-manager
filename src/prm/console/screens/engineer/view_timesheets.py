"""Screen 5.2 — View my timesheets."""

from prm.console.client import ApiError, PrmApiClient
from prm.console.screens.engineer._helpers import timesheet_status_label
from prm.console.session import UserSession
from prm.console.ui import (
    clear_screen,
    pause,
    print_banner,
    print_divider,
    print_error,
    read_line,
)
from prm.console.ui.dates import format_date_input, parse_date


def run(client: PrmApiClient, session: UserSession) -> None:
    while True:
        clear_screen()
        print_banner("MY TIMESHEETS")
        try:
            result = client.list_my_timesheets(session.access_token)
        except ApiError as exc:
            print_error(str(exc))
            pause()
            return

        print(f"{'Week Start':<16}{'Total Hrs':<12}{'Status'}")
        print_divider()
        if result.weeks:
            for week in result.weeks:
                print(
                    f"{format_date_input(week.week_start_date):<16}"
                    f"{week.total_hours} hrs{'':<5}"
                    f"{timesheet_status_label(week.status)}"
                )
        else:
            print("(no timesheets yet)")
        print_divider()
        print()
        print("[V] View week details     [B] Back")
        action = read_line("Enter action: ").strip().upper()
        if action in {"B", "BACK"}:
            return
        if action in {"V", "VIEW"}:
            _view_week_detail(client, session)
            continue
        print_error("Enter V to view details or B to go back.")
        pause()


def _view_week_detail(client: PrmApiClient, session: UserSession) -> None:
    raw = read_line("Enter week start (DD-MM-YYYY): ").strip()
    week_start = parse_date(raw)
    if week_start is None:
        print_error("Invalid date.")
        pause()
        return

    try:
        detail = client.get_my_timesheet_detail(session.access_token, week_start)
    except ApiError as exc:
        print_error(str(exc))
        pause()
        return

    clear_screen()
    print_banner("WEEK DETAIL")
    print(
        f"── Week: {format_date_input(detail.week_start_date)} — "
        f"Status: {timesheet_status_label(detail.status)} ─────"
    )
    print()
    if detail.entries:
        print(f"{'Project':<16}{'Hrs':<8}{'Activity Tags'}")
        print_divider()
        for entry in detail.entries:
            tags = ", ".join(entry.activity_tags) if entry.activity_tags else "-"
            print(f"{entry.project_name:<16}{entry.hours_worked:<8}{tags}")
        print_divider()
    else:
        print("No project entries for this week.")
    print(f"Total: {detail.total_hours} hrs")
    print()
    print("[B] Back")
    read_line()
    pause()
