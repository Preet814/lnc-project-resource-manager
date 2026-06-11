"""Screen 5 — Engineer panel (BRD Employee menu)."""

from prm.console.client import ApiError, PrmApiClient
from prm.console.screens.engineer import (
    submit_timesheet,
    view_allocations,
    view_timesheets,
)
from prm.console.screens.engineer._helpers import timesheet_reminder_week
from prm.console.session import UserSession
from prm.console.ui import (
    clear_screen,
    format_header_datetime,
    pause,
    print_banner,
    print_divider,
    print_error,
    read_option,
)
from prm.console.ui.dates import format_date_input


def run(client: PrmApiClient, session: UserSession) -> str:
    """Run engineer menu until logout. Returns 'logout'."""
    while True:
        clear_screen()
        header = f"Welcome, {session.full_name}!  |  {format_header_datetime()}"
        print_banner("ENGINEER PANEL", subtitle=header)
        _print_timesheet_reminder(client, session)
        print("1. Submit Timesheet")
        print("2. View My Timesheets")
        print("3. View My Allocations")
        print("4. Logout")
        print()
        choice = read_option()

        if choice == "4":
            return "logout"
        if choice == "1":
            submit_timesheet.run(client, session)
        elif choice == "2":
            view_timesheets.run(client, session)
        elif choice == "3":
            view_allocations.run(client, session)
        else:
            print_error("Invalid option. Choose 1–4.")
            pause()


def _print_timesheet_reminder(client: PrmApiClient, session: UserSession) -> None:
    try:
        timesheets = client.list_my_timesheets(session.access_token)
    except ApiError:
        return

    reminder_week = timesheet_reminder_week(timesheets.weeks)
    if reminder_week is None:
        return

    try:
        week_allocations = client.list_allocations_for_week(
            session.access_token,
            week_start_date=reminder_week,
        )
    except ApiError:
        return

    if not week_allocations.allocations:
        return

    print(
        f"  ⚠  Reminder: Timesheet for week {format_date_input(reminder_week)} "
        "has not been submitted."
    )
    print_divider()
    print()
