"""Screen 4.5 — AI assistant (skill match and risk summary)."""

from prm.console.client import ApiError, PrmApiClient
from prm.console.screens.manager._helpers import (
    health_label,
    load_manager_projects,
    select_project,
    select_project_by_number,
)
from prm.console.session import UserSession
from prm.console.ui import (
    clear_screen,
    pause,
    print_banner,
    print_error,
    read_line,
    read_option,
)


def run(client: PrmApiClient, session: UserSession) -> None:
    while True:
        clear_screen()
        print_banner("AI ASSISTANT")
        print("1. Skill Match    — Find best employees for a project requirement")
        print("2. Risk Summary   — Get a health analysis for a project")
        print("3. Back")
        print()
        choice = read_option()

        if choice == "3":
            return
        if choice == "1":
            _skill_match(client, session)
        elif choice == "2":
            _risk_summary(client, session)
        else:
            print_error("Invalid option. Choose 1–3.")
            pause()


def _skill_match(client: PrmApiClient, session: UserSession) -> None:
    clear_screen()
    print_banner("SKILL MATCH")
    project = select_project(client, session, prompt="Select project (name or ID): ")
    if project is None:
        pause()
        return

    print("\nDescribe your project requirement in plain English:")
    requirement = read_line("> ")
    if not requirement:
        print_error("Requirement cannot be empty.")
        pause()
        return

    print("\nSearching... (calling AI)")
    try:
        result = client.skill_match(session.access_token, project.project_id, requirement)
    except ApiError as exc:
        print_error(str(exc))
        pause()
        return

    clear_screen()
    print_banner("SKILL MATCH RESULTS")
    if result.message and not result.matches:
        print(result.message)
    elif not result.matches:
        print("No matches found.")
    else:
        print("Results:")
        for index, match in enumerate(result.matches, start=1):
            print(f"  {index}.  {match.user_name}")
            print(f"      Reason: {match.reason}")
            print(
                f"      Suggested allocation: {match.suggested_allocation_percent}%  "
                f"({match.free_hours_per_week} free hrs/week)"
            )
            print()
        print(
            "  Note: These are AI-generated suggestions. Always verify availability\n"
            "  and skills with the employee before allocating."
        )
    print()
    print("[A] Go to Allocate Resource     [B] Back")
    action = read_line("Enter action: ").strip().upper()
    if action in {"A", "ALLOCATE"}:
        from prm.console.screens.manager import allocate_resource

        allocate_resource.run(client, session)


def _risk_summary(client: PrmApiClient, session: UserSession) -> None:
    clear_screen()
    print_banner("RISK SUMMARY")
    projects = load_manager_projects(client, session)
    if projects is None:
        pause()
        return
    if not projects:
        print("No projects assigned to you.")
        pause()
        return

    print("Select project:")
    for index, project in enumerate(projects, start=1):
        print(f"  {index}.  {project.name}    {health_label(project.health_status)}")
    print()
    raw = read_line("Enter project number: ").strip()
    if not raw.isdigit():
        print_error("Invalid project number.")
        pause()
        return

    project = select_project_by_number(projects, int(raw))
    if project is None:
        print_error("Project not found.")
        pause()
        return

    print("\nGenerating AI summary...")
    try:
        summary = client.get_risk_summary(session.access_token, project.project_id)
    except ApiError as exc:
        print_error(str(exc))
        pause()
        return

    clear_screen()
    print_banner(f"RISK SUMMARY — {project.name}")
    print()
    print(f"\"{summary.summary}\"")
    print()
    print(f"  Note: {summary.disclaimer}")
    print()
    print("[B] Back")
    read_line()
    pause()
