"""Screen 5.1 — Submit timesheet."""

from dataclasses import dataclass

from prm.console.client import ApiError, PrmApiClient
from prm.console.screens.engineer._helpers import (
    default_week_start,
    format_activity_tags,
    parse_activity_tags,
    print_activity_tag_menu,
)
from prm.console.session import UserSession
from prm.console.ui import (
    clear_screen,
    pause,
    print_banner,
    print_divider,
    print_error,
    print_success,
    read_line,
    read_save_or_back,
)
from prm.console.ui.dates import format_date_input, parse_date
from prm.domain.enums import ActivityTag


@dataclass
class _ProjectEntry:
    project_id: int
    project_name: str
    utilisation_percent: int
    expected_max_hours: int
    hours_worked: int
    activity_tags: tuple[ActivityTag, ...]


def run(client: PrmApiClient, session: UserSession) -> None:
    clear_screen()
    print_banner("SUBMIT TIMESHEET")
    print(f"Employee  : {session.full_name}")
    week_raw = read_line(
        "Week Start: Enter date (DD-MM-YYYY) or press Enter for last Monday\n          > "
    )
    week_start = parse_date(week_raw) if week_raw.strip() else default_week_start()
    if week_start is None:
        print_error("Invalid week start date. Use DD-MM-YYYY (must be a Monday).")
        pause()
        return

    print("\nChecking your active allocations for this week...")
    try:
        week_allocations = client.list_allocations_for_week(
            session.access_token,
            week_start_date=week_start,
        )
    except ApiError as exc:
        print_error(str(exc))
        pause()
        return

    if not week_allocations.allocations:
        print_error("You have no active project allocations for this week.")
        pause()
        return

    entries: list[_ProjectEntry] = []
    total = len(week_allocations.allocations)
    for index, allocation in enumerate(week_allocations.allocations, start=1):
        clear_screen()
        print_banner("SUBMIT TIMESHEET")
        print_divider()
        print(f"PROJECT {index} OF {total} — {allocation.project_name}")
        print(
            f"  Allocation: {allocation.utilisation_percent}%   |   "
            f"Expected: {allocation.expected_max_hours} hrs max"
        )
        print_divider()
        hours_raw = read_line("Hours worked this week: ").strip()
        if not hours_raw.isdigit():
            print_error("Hours must be a non-negative number.")
            pause()
            return
        hours = int(hours_raw)
        tags: tuple[ActivityTag, ...] = ()
        if hours > 0:
            print()
            print_activity_tag_menu()
            tags_raw = read_line("Select tags (comma-separated): ")
            parsed = parse_activity_tags(tags_raw)
            if not parsed:
                print_error("At least one activity tag is required when logging hours.")
                pause()
                return
            tags = tuple(parsed)
        entries.append(
            _ProjectEntry(
                project_id=allocation.project_id,
                project_name=allocation.project_name,
                utilisation_percent=allocation.utilisation_percent,
                expected_max_hours=allocation.expected_max_hours,
                hours_worked=hours,
                activity_tags=tags,
            )
        )

    total_hours = sum(entry.hours_worked for entry in entries)
    clear_screen()
    print_banner("SUMMARY")
    for entry in entries:
        if entry.hours_worked > 0:
            tag_labels = [t.value.replace("_", " ").title() for t in entry.activity_tags]
            print(
                f"  {entry.project_name:<16}{entry.hours_worked} hrs    "
                f"[{format_activity_tags(tag_labels)}]"
            )
    print("  ─────────────────────────────────────────")
    max_hours = week_allocations.max_weekly_hours
    valid = "✓" if total_hours <= max_hours else "✗"
    print(f"  Total           {total_hours} hrs / {max_hours} hrs max   {valid}")
    print()
    print_divider()
    print("[S] Submit Timesheet     [B] Back")
    if read_save_or_back() is None:
        return

    payload = [
        {
            "project_id": entry.project_id,
            "hours_worked": entry.hours_worked,
            "activity_tags": [tag.value for tag in entry.activity_tags],
        }
        for entry in entries
        if entry.hours_worked > 0
    ]
    if not payload and total_hours == 0:
        print_error("Enter hours for at least one project or go back.")
        pause()
        return

    try:
        result = client.submit_timesheet(
            session.access_token,
            week_start_date=week_start,
            entries=payload,
        )
    except ApiError as exc:
        print_error(str(exc))
        pause()
        return

    print_success(
        f"Timesheet submitted successfully. Status: {result.status.value} ✓\n"
        f"Week: {format_date_input(result.week_start_date)}  |  Total: {result.total_hours} hrs"
    )
    pause()
