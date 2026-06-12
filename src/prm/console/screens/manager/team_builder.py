"""Screen 4.5 — Team Builder (plain-English whole-team staffing)."""

from prm.console.client import ApiError, PrmApiClient
from prm.console.client.models import TeamMatchResult, TeamSlotAssignment, TeamSlotGap
from prm.console.screens.manager._helpers import select_project
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
from prm.domain.enums import TeamGapType


def run(client: PrmApiClient, session: UserSession) -> None:
    clear_screen()
    print_banner("TEAM BUILDER")
    project = select_project(client, session, prompt="Select project (name or ID): ")
    if project is None:
        pause()
        return

    print("\nDescribe the whole team you need in one paragraph:")
    print("(e.g. Banking portal needs Senior Java Developer, DevOps Engineer, QA Tester)")
    requirement = read_line("> ")
    if not requirement:
        print_error("Requirement cannot be empty.")
        pause()
        return

    print("\nBuilding team... (parsing requirement and matching your team)")
    try:
        result = client.team_match(session.access_token, project.project_id, requirement)
    except ApiError as exc:
        print_error(str(exc))
        pause()
        return

    clear_screen()
    print_banner(f"TEAM BUILDER RESULTS — {project.name}")
    print()
    print(f"Requirement: {result.requirement}")
    print()
    _print_assignments(result.assignments)
    _print_gaps(result.gaps)
    print(
        "  Note: Assignments are chosen by system rules. Reasons are AI-generated.\n"
        "  Gaps are factual (skill or availability). Verify before allocating."
    )
    print()
    print("[A] Go to Allocate Resource     [B] Back")
    action = read_line("Enter action: ").strip().upper()
    if action in {"A", "ALLOCATE"}:
        from prm.console.screens.manager import allocate_resource

        allocate_resource.run(client, session)
    else:
        pause()


def _print_assignments(assignments: tuple[TeamSlotAssignment, ...]) -> None:
    if not assignments:
        print("No roles were filled.")
        print()
        return

    print("Filled roles:")
    print_divider()
    for assignment in assignments:
        position_label = (
            f"{assignment.role_label} (#{assignment.position})"
            if assignment.position > 1
            else assignment.role_label
        )
        print(f"  Role:       {position_label}")
        print(f"  Person:     {assignment.user_name}")
        print(
            f"  Allocation: {assignment.suggested_allocation_percent}%  "
            f"({assignment.free_hours_per_week} free hrs/week)"
        )
        print(f"  Reason:     {assignment.reason}")
        print()


def _print_gaps(gaps: tuple[TeamSlotGap, ...]) -> None:
    if not gaps:
        return

    print("Unfilled roles:")
    print_divider()
    for gap in gaps:
        position_label = (
            f"{gap.role_label} (#{gap.position})"
            if gap.position > 1
            else gap.role_label
        )
        gap_label = _gap_type_label(gap.gap_type)
        print(f"  Role:     {position_label}")
        print(f"  Gap:      {gap_label}")
        print(f"  Detail:   {gap.detail}")
        for hint in gap.availability_hints:
            if hint.available_from is not None:
                print(
                    f"            {hint.user_name} available from "
                    f"{format_date(hint.available_from)}"
                )
            else:
                print(f"            {hint.user_name} — availability unknown")
        print()


def _gap_type_label(gap_type: TeamGapType) -> str:
    labels = {
        TeamGapType.SKILL_GAP: "SKILL GAP",
        TeamGapType.AVAILABILITY_GAP: "AVAILABILITY GAP",
    }
    return labels.get(gap_type, gap_type.value)
