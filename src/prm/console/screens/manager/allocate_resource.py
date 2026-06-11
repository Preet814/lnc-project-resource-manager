"""Screen 4.2 — Allocate resource (AI, direct, end)."""

from datetime import date

from prm.console.client import ApiError, PrmApiClient
from prm.console.client.models import ManagerProjectSummary, SkillMatchResult
from prm.console.screens.admin._helpers import confirm_action, read_int
from prm.console.screens.manager._helpers import select_project
from prm.console.session import UserSession
from prm.console.ui import (
    clear_screen,
    pause,
    print_banner,
    print_divider,
    print_error,
    print_success,
    read_line,
    read_option,
)
from prm.console.ui.dates import format_date, parse_date


def run(client: PrmApiClient, session: UserSession) -> None:
    while True:
        clear_screen()
        print_banner("ALLOCATE RESOURCE")
        print("1. Find resource using AI (recommended)")
        print("2. Allocate directly (I already know who I want)")
        print("3. End an existing allocation")
        print("4. Back")
        print()
        choice = read_option()

        if choice == "4":
            return
        if choice == "1":
            _ai_allocate(client, session)
        elif choice == "2":
            _direct_allocate(client, session)
        elif choice == "3":
            _end_allocation(client, session)
        else:
            print_error("Invalid option. Choose 1–4.")
            pause()


def _ai_allocate(client: PrmApiClient, session: UserSession) -> None:
    clear_screen()
    print_banner("ALLOCATE RESOURCE — AI MATCH")
    print("Step 1 — Select Project")
    project = select_project(client, session)
    if project is None:
        pause()
        return

    print("\nStep 2 — Describe your requirement")
    print("Type what kind of resource you need:")
    requirement = read_line("> ")
    if not requirement:
        print_error("Requirement cannot be empty.")
        pause()
        return

    print("\nSearching... (AI matching in progress)")
    try:
        result = client.skill_match(session.access_token, project.project_id, requirement)
    except ApiError as exc:
        print_error(str(exc))
        pause()
        return

    if result.message and not result.matches:
        print(f"\n{result.message}")
        pause()
        return

    if not result.matches:
        print_error("No matches found. Try a different requirement.")
        pause()
        return

    _show_matches_and_allocate(client, session, project, result.matches)


def _show_matches_and_allocate(
    client: PrmApiClient,
    session: UserSession,
    project: ManagerProjectSummary,
    matches: tuple[SkillMatchResult, ...],
) -> None:
    while True:
        clear_screen()
        print_banner("AI-MATCHED RESULTS")
        print_divider()
        print(f"{'#':<4}{'Name':<16}{'Avail %':<10}{'Free Hrs/Wk'}")
        for index, match in enumerate(matches, start=1):
            print(
                f"{index:<4}{match.user_name:<16}"
                f"{match.suggested_allocation_percent}%{'':<6}"
                f"{match.free_hours_per_week}"
            )
        print()
        for index, match in enumerate(matches, start=1):
            print(f"  {index}. {match.user_name}")
            print(f"     Reason: {match.reason}")
        print()
        print("Note: Suggestions are AI-generated. Verify before confirming.")
        print_divider()
        raw = read_line("Select employee (enter #, or 0 to cancel): ").strip()
        if raw == "0":
            return
        if not raw.isdigit():
            print_error("Enter a number from the list.")
            pause()
            continue
        choice = int(raw)
        if choice < 1 or choice > len(matches):
            print_error("Invalid selection.")
            pause()
            continue
        match = matches[choice - 1]
        if _submit_allocation_form(
            client,
            session,
            project,
            user_id=match.user_id,
            user_name=match.user_name,
            suggested_percent=match.suggested_allocation_percent,
        ):
            return


def _direct_allocate(client: PrmApiClient, session: UserSession) -> None:
    clear_screen()
    print_banner("DIRECT ALLOCATION")
    project = select_project(client, session, prompt="Select Project (name or ID): ")
    if project is None:
        pause()
        return

    user_id = read_int("Enter Employee ID : ")
    if user_id is None:
        pause()
        return

    user_name = str(user_id)
    try:
        detail = client.get_engineer_resource_detail(session.access_token, user_id)
        user_name = detail.full_name
        print(f"\n── {detail.full_name} ─────────────────────────────────")
        print(f"Current Utilisation: {detail.current_utilisation_percent}%")
    except ApiError:
        pass

    _submit_allocation_form(
        client,
        session,
        project,
        user_id=user_id,
        user_name=user_name,
        suggested_percent=None,
    )


def _submit_allocation_form(
    client: PrmApiClient,
    session: UserSession,
    project: ManagerProjectSummary,
    *,
    user_id: int,
    user_name: str,
    suggested_percent: int | None,
) -> bool:
    clear_screen()
    print_banner("SET ALLOCATION")
    print(f"Project : {project.name} ({project.project_id})")
    print(f"Employee: {user_name} ({user_id})")
    percent_prompt = "Utilisation %   : "
    if suggested_percent is not None:
        percent_prompt = f"Utilisation %   : [{suggested_percent}] "
    percent_raw = read_line(percent_prompt).strip() or (
        str(suggested_percent) if suggested_percent is not None else ""
    )
    from_raw = read_line("From Date       : (DD-MM-YYYY) ")
    to_raw = read_line("To Date         : (DD-MM-YYYY) ")
    print()
    print_divider()
    print("[C] Confirm Allocation     [B] Back")
    action = read_line("Enter action: ").strip().upper()
    if action not in {"C", "CONFIRM"}:
        return False

    if not percent_raw.isdigit():
        print_error("Utilisation must be a number between 1 and 100.")
        pause()
        return False

    from_date = parse_date(from_raw)
    to_date = parse_date(to_raw) if to_raw.strip() else None
    if from_date is None:
        print_error("From date is required (DD-MM-YYYY).")
        pause()
        return False

    try:
        client.create_allocation(
            session.access_token,
            project_id=project.project_id,
            user_id=user_id,
            utilisation_percent=int(percent_raw),
            from_date=from_date,
            to_date=to_date,
        )
    except ApiError as exc:
        print_error(str(exc))
        pause()
        return False

    end_label = format_date(to_date) if to_date else "open-ended"
    print_success(
        f"Allocation saved. {user_name} → {project.name} "
        f"({percent_raw}%, {format_date(from_date)}–{end_label}) ✓"
    )
    pause()
    return True


def _end_allocation(client: PrmApiClient, session: UserSession) -> None:
    clear_screen()
    print_banner("END ALLOCATION")
    project = select_project(client, session, prompt="Select Project: ")
    if project is None:
        pause()
        return

    try:
        allocations = client.list_project_allocations(
            session.access_token,
            project.project_id,
        )
    except ApiError as exc:
        print_error(str(exc))
        pause()
        return

    if not allocations.allocations:
        print_error("No active allocations on this project.")
        pause()
        return

    print(f"\nActive Allocations on {project.name}:")
    print(f"  {'#':<4}{'Employee':<16}{'%':<6}{'From':<12}{'To'}")
    for index, allocation in enumerate(allocations.allocations, start=1):
        print(
            f"  {index:<4}{allocation.user_full_name:<16}"
            f"{allocation.utilisation_percent}%{'':<3}"
            f"{format_date(allocation.from_date):<12}{format_date(allocation.to_date)}"
        )
    print_divider()

    raw = read_line("Select allocation to end: ").strip()
    if not raw.isdigit():
        print_error("Invalid selection.")
        pause()
        return
    choice = int(raw)
    if choice < 1 or choice > len(allocations.allocations):
        print_error("Invalid allocation number.")
        pause()
        return

    allocation = allocations.allocations[choice - 1]
    today = date.today()
    if not confirm_action(
        f"End {allocation.user_full_name}'s allocation on {project.name}?\n"
        f"Set end date to today ({format_date(today)})?"
    ):
        return

    try:
        client.end_allocation(
            session.access_token,
            allocation.allocation_id,
            as_of=today,
        )
    except ApiError as exc:
        print_error(str(exc))
        pause()
        return

    print_success(
        f"Allocation ended. {allocation.user_full_name} freed from {project.name} "
        f"as of {format_date(today)}. ✓\n"
        "Employee status updated to BENCH if no other active allocations remain."
    )
    pause()
