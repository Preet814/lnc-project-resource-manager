"""Screen 3.2 — Manage projects and milestones."""

from prm.console.client import ApiError, PrmApiClient
from prm.console.screens.admin._helpers import read_int, read_optional_line
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
    read_save_or_back,
)
from prm.console.ui.choices import MILESTONE_STATUS_CHOICES, PROJECT_STATUS_CHOICES
from prm.console.ui.dates import format_date, format_date_input, parse_date
from prm.domain.enums import ProjectStatus


def run(client: PrmApiClient, session: UserSession) -> None:
    while True:
        clear_screen()
        print_banner("MANAGE PROJECTS")
        print("1. Create Project")
        print("2. View All Projects")
        print("3. Update Project Details")
        print("4. Manage Milestones")
        print("5. Back")
        print()
        choice = read_option()

        if choice == "5":
            return
        if choice == "1":
            _create_project(client, session)
        elif choice == "2":
            _view_projects(client, session)
        elif choice == "3":
            _update_project(client, session)
        elif choice == "4":
            _manage_milestones(client, session)
        else:
            print_error("Invalid option. Choose 1–5.")
            pause()


def _create_project(client: PrmApiClient, session: UserSession) -> None:
    clear_screen()
    print_banner("CREATE PROJECT")
    name = read_line("Project Name        : ")
    description = read_line("Description         : ") or None
    start_raw = read_line("Start Date          : (DD-MM-YYYY) ")
    end_raw = read_line("End Date            : (DD-MM-YYYY) ")
    print("Status              : (1) PLANNED   (2) ACTIVE   (3) ON_HOLD")
    status_choice = read_line("Select status       : ")
    manager_raw = read_line("Assign Manager      : (Enter Manager ID) ")
    story_points_raw = read_line("Total Story Points  : ")
    print()
    print_divider()
    print("[S] Save     [B] Back")
    if read_save_or_back() is None:
        return

    start_date = parse_date(start_raw)
    status = PROJECT_STATUS_CHOICES.get(status_choice)
    if not name or start_date is None or status is None or not manager_raw.isdigit():
        print_error("Project name, start date, status, and manager ID are required.")
        pause()
        return

    end_date = parse_date(end_raw) if end_raw.strip() else None
    try:
        total_story_points = int(story_points_raw) if story_points_raw.strip() else 0
        created = client.create_project(
            session.access_token,
            name=name,
            description=description,
            start_date=start_date,
            end_date=end_date,
            status=status,
            manager_user_id=int(manager_raw),
            total_story_points=total_story_points,
        )
    except (ApiError, ValueError) as exc:
        print_error(str(exc))
        pause()
        return

    print_success(f"Project created. ID: {created.id}  |  Name: {created.name} ✓")
    pause()


def _view_projects(client: PrmApiClient, session: UserSession) -> None:
    clear_screen()
    print_banner("ALL PROJECTS")
    try:
        result = client.list_projects(session.access_token)
    except ApiError as exc:
        print_error(str(exc))
        pause()
        return

    print(
        f"{'ID':<5}{'Name':<18}{'Manager':<14}{'End Date':<12}"
        f"{'Status':<10}{'SP Done/Total'}"
    )
    print_divider(78)
    for project in result.projects:
        end = format_date(project.end_date)
        sp = f"{project.story_points_done} / {project.story_points_total}"
        print(
            f"{project.id:<5}{project.name:<18}{project.manager_full_name:<14}"
            f"{end:<12}{project.status.value:<10}{sp}"
        )
    print_divider(78)
    print(f"Total: {result.total}")
    print()
    print("[B] Back")
    read_line()
    pause()


def _update_project(client: PrmApiClient, session: UserSession) -> None:
    clear_screen()
    print_banner("UPDATE PROJECT DETAILS")
    project_id = read_int("Enter Project ID: ")
    if project_id is None:
        pause()
        return

    try:
        project = client.get_project(session.access_token, project_id)
    except ApiError as exc:
        print_error(str(exc))
        pause()
        return

    print(f"\n── {project.name} ───────────────────────────────")
    name = read_optional_line("Project Name", project.name)
    description = read_optional_line("Description", project.description or "")
    start_raw = read_line(f"Start Date [{format_date_input(project.start_date)}]: ")
    end_raw = read_line(f"End Date [{format_date_input(project.end_date)}]: ")
    print("Status : (1) PLANNED   (2) ACTIVE   (3) ON_HOLD   (4) COMPLETED")
    status_choice = read_line(f"Select status [{project.status.value}]: ")
    manager_raw = read_line(f"Assign Manager ID [{project.manager_user_id}]: ")
    story_points_raw = read_line(f"Total Story Points [{project.total_story_points}]: ")
    print()
    print_divider()
    print("[S] Save     [B] Back")
    if read_save_or_back() is None:
        return

    status = PROJECT_STATUS_CHOICES.get(status_choice) if status_choice else None
    start_date = parse_date(start_raw) if start_raw else None
    end_date = parse_date(end_raw) if end_raw else None
    manager_user_id = int(manager_raw) if manager_raw.isdigit() else None
    total_story_points = int(story_points_raw) if story_points_raw.isdigit() else None

    try:
        client.update_project(
            session.access_token,
            project_id,
            name=name,
            description=description if description is not None else None,
            start_date=start_date,
            end_date=end_date,
            status=status,
            manager_user_id=manager_user_id,
            total_story_points=total_story_points,
        )
    except (ApiError, ValueError) as exc:
        print_error(str(exc))
        pause()
        return

    print_success("Project updated. ✓")
    pause()


def _manage_milestones(client: PrmApiClient, session: UserSession) -> None:
    clear_screen()
    print_banner("MILESTONES")
    project_id = read_int("Enter Project ID: ")
    if project_id is None:
        pause()
        return

    try:
        project = client.get_project(session.access_token, project_id)
    except ApiError as exc:
        print_error(str(exc))
        pause()
        return

    while True:
        clear_screen()
        print_banner("MILESTONES")
        print(f"── {project.name} ───────────────────────────────")
        try:
            milestones = client.list_milestones(session.access_token, project_id)
        except ApiError as exc:
            print_error(str(exc))
            pause()
            return

        print(f"{'#':<4}{'Title':<20}{'Due Date':<12}{'Story Pts':<10}{'Status'}")
        print_divider(62)
        for milestone in milestones.milestones:
            print(
                f"{milestone.sequence_order:<4}{milestone.title:<20}"
                f"{format_date(milestone.due_date):<12}{milestone.story_points:<10}"
                f"{milestone.status.value}"
            )
        print_divider(62)
        print(
            f"Total: {milestones.total_story_points} SP   |   "
            f"Completed: {milestones.completed_story_points} SP   |   "
            f"Remaining: {milestones.remaining_story_points} SP"
        )
        print()
        print("1. Add Milestone")
        print("2. Update Milestone Status")
        print("3. Back")
        print()
        choice = read_option()

        if choice == "3":
            return
        if choice == "1":
            _add_milestone(client, session, project_id)
        elif choice == "2":
            _update_milestone_status(client, session, project_id, milestones.milestones)
        else:
            print_error("Invalid option. Choose 1–3.")
            pause()


def _add_milestone(client: PrmApiClient, session: UserSession, project_id: int) -> None:
    clear_screen()
    print_banner("ADD MILESTONE")
    title = read_line("Milestone Title  : ")
    due_raw = read_line("Due Date         : (DD-MM-YYYY) ")
    story_points_raw = read_line("Story Points     : ")
    due_date = parse_date(due_raw)
    if not title or due_date is None:
        print_error("Title and due date are required.")
        pause()
        return
    try:
        story_points = int(story_points_raw) if story_points_raw.strip() else 0
        client.add_milestone(
            session.access_token,
            project_id,
            title=title,
            due_date=due_date,
            story_points=story_points,
        )
    except (ApiError, ValueError) as exc:
        print_error(str(exc))
        pause()
        return
    print_success("Milestone added. ✓")
    pause()


def _update_milestone_status(client, session, project_id, milestones) -> None:
    if not milestones:
        print_error("No milestones to update.")
        pause()
        return
    index = read_int("Enter Milestone # : ")
    if index is None:
        pause()
        return
    milestone = next((item for item in milestones if item.sequence_order == index), None)
    if milestone is None:
        print_error("Milestone not found.")
        pause()
        return
    print("New Status : (1) NOT_STARTED   (2) IN_PROGRESS   (3) DONE")
    status_choice = read_line("Select status: ")
    status = MILESTONE_STATUS_CHOICES.get(status_choice)
    if status is None:
        print_error("Invalid status choice.")
        pause()
        return
    try:
        client.update_milestone_status(
            session.access_token,
            project_id,
            milestone.milestone_id,
            status=status,
        )
    except ApiError as exc:
        print_error(str(exc))
        pause()
        return
    print_success("Milestone updated. ✓")
    pause()
