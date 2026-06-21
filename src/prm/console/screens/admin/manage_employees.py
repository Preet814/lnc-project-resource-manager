"""Screen 3.1 — Manage engineers (BRD Manage Employees)."""

from prm.console.client import ApiError, PrmApiClient
from prm.console.screens.admin._helpers import (
    confirm_action,
    display_value,
    read_int,
    read_optional_line,
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
    read_option,
    read_save_or_back,
)
from prm.console.ui.choices import (
    PROFICIENCY_CHOICES,
    SKILL_CATEGORY_CHOICES,
    WORK_STATUS_CHOICES,
)
from prm.console.ui.dates import format_date
from prm.domain.enums import ResourceWorkStatus


def run(client: PrmApiClient, session: UserSession) -> None:
    while True:
        clear_screen()
        print_banner("MANAGE EMPLOYEES")
        print("1. View All Employees")
        print("2. Update Employee")
        print("3. Deactivate Employee")
        print("4. Manage Employee Skills")
        print("5. Assign Manager")
        print("6. Back")
        print()
        choice = read_option()

        if choice == "6":
            return
        if choice == "1":
            _view_all_employees(client, session)
        elif choice == "2":
            _update_employee(client, session)
        elif choice == "3":
            _deactivate_employee(client, session)
        elif choice == "4":
            _manage_skills(client, session)
        elif choice == "5":
            _assign_manager(client, session)
        else:
            print_error("Invalid option. Choose 1–6.")
            pause()


def _view_all_employees(client: PrmApiClient, session: UserSession) -> None:
    work_status: ResourceWorkStatus | None = None
    department: str | None = None

    while True:
        clear_screen()
        print_banner("ALL EMPLOYEES")
        try:
            result = client.list_employees(
                session.access_token,
                work_status=work_status,
                department=department,
            )
        except ApiError as exc:
            print_error(str(exc))
            pause()
            return

        print(f"{'ID':<5}{'Name':<16}{'Department':<14}{'Designation':<12}{'Status':<10}{'Email OK'}")
        print_divider(68)
        for engineer in result.engineers:
            verified = "Yes" if engineer.email_verified else "No"
            print(
                f"{engineer.id:<5}{engineer.full_name:<16}"
                f"{display_value(engineer.department):<14}"
                f"{display_value(engineer.designation):<12}"
                f"{engineer.work_status.value:<10}"
                f"{verified}"
            )
        print_divider(68)
        print(
            f"Total: {result.total}   |   Allocated: {result.allocated_count}   |   "
            f"Bench: {result.bench_count}"
        )
        if work_status or department:
            filters = []
            if work_status:
                filters.append(f"status={work_status.value}")
            if department:
                filters.append(f"department={department}")
            print(f"Filters: {', '.join(filters)}")
        print()
        print("[F] Filter by Status / Department     [B] Back")
        action = read_line("Enter action: ").strip().upper()
        if action in {"B", "BACK"}:
            return
        if action in {"F", "FILTER"}:
            work_status, department = _read_employee_filters()
            continue
        print_error("Enter F to filter or B to go back.")
        pause()


def _read_employee_filters() -> tuple[ResourceWorkStatus | None, str | None]:
    clear_screen()
    print_banner("FILTER EMPLOYEES")
    print("Work Status: (1) BENCH   (2) ALLOCATED   [Enter] Clear")
    status_choice = read_line("Select status: ").strip()
    work_status = WORK_STATUS_CHOICES.get(status_choice)
    department = read_line("Department name (blank = any): ").strip() or None
    return work_status, department


def _update_employee(client: PrmApiClient, session: UserSession) -> None:
    clear_screen()
    print_banner("UPDATE EMPLOYEE")
    user_id = read_int("Enter Employee ID: ")
    if user_id is None:
        pause()
        return

    try:
        employee = client.get_employee(session.access_token, user_id)
    except ApiError as exc:
        print_error(str(exc))
        pause()
        return

    print(f"\n── {employee.full_name} ─────────────────────────────────")
    full_name = read_optional_line("Full Name", employee.full_name)
    email = read_optional_line("Email", employee.email)
    department = read_optional_line("Department", employee.department)
    designation = read_optional_line("Designation", employee.designation)
    print()
    print_divider()
    print("[S] Save     [B] Back")
    if read_save_or_back() is None:
        return

    try:
        client.update_employee(
            session.access_token,
            user_id,
            full_name=full_name,
            email=email,
            department=department,
            designation=designation,
        )
    except ApiError as exc:
        print_error(str(exc))
        pause()
        return

    print_success("Employee updated. ✓")
    pause()


def _deactivate_employee(client: PrmApiClient, session: UserSession) -> None:
    clear_screen()
    print_banner("DEACTIVATE EMPLOYEE")
    user_id = read_int("Enter Employee ID: ")
    if user_id is None:
        pause()
        return

    try:
        employee = client.get_employee(session.access_token, user_id)
        allocations = client.list_allocations(session.access_token, user_id=user_id)
    except ApiError as exc:
        print_error(str(exc))
        pause()
        return

    print(f"\n── {employee.full_name} ─────────────────────────────────")
    print(f"Department : {employee.department}")
    print(f"Status     : {employee.work_status.value} ({employee.current_utilisation_percent}%)")
    if allocations.allocations:
        count = len(allocations.allocations)
        print(f"\n⚠  Warning: This employee has {count} active allocation(s).")
        print("   Ending their employment will remove them from:")
        for allocation in allocations.allocations:
            end = format_date(allocation.to_date)
            print(
                f"     - {allocation.project_name}  "
                f"({allocation.utilisation_percent}%,  ends {end})"
            )

    if not confirm_action(
        f"Are you sure you want to deactivate {employee.full_name}?\n"
        "This will: set account inactive, end all active allocations today,\n"
        "and block their login account."
    ):
        return

    try:
        client.deactivate_employee(session.access_token, user_id)
    except ApiError as exc:
        print_error(str(exc))
        pause()
        return

    print_success("Employee deactivated. ✓")
    pause()


def _manage_skills(client: PrmApiClient, session: UserSession) -> None:
    clear_screen()
    print_banner("MANAGE SKILLS")
    user_id = read_int("Enter Employee ID: ")
    if user_id is None:
        pause()
        return

    try:
        employee = client.get_employee(session.access_token, user_id)
        skills = client.list_user_skills(session.access_token, user_id)
    except ApiError as exc:
        print_error(str(exc))
        pause()
        return

    while True:
        clear_screen()
        print_banner("MANAGE SKILLS")
        print(f"── {employee.full_name} ─────────────────────────────────")
        if skills:
            print("Current Skills:")
            for index, skill in enumerate(skills, start=1):
                print(f"  {index}.  {skill.skill_name:<18}{skill.proficiency.value}")
        else:
            print("Current Skills: (none)")
        print_divider()
        print("1. Add Skill")
        print("2. Update Proficiency Level")
        print("3. Remove Skill")
        print("4. Back")
        print()
        choice = read_option()

        if choice == "4":
            return
        if choice == "1":
            skills = _add_skill(client, session, user_id, skills)
        elif choice == "2":
            skills = _update_skill_proficiency(client, session, user_id, skills)
        elif choice == "3":
            skills = _remove_skill(client, session, user_id, skills)
        else:
            print_error("Invalid option. Choose 1–4.")
            pause()


def _add_skill(client, session, user_id, skills):
    clear_screen()
    print_banner("ADD SKILL")
    skill_name = read_line("Skill Name        : ")
    print("Category          : (1) Backend  (2) Frontend  (3) DevOps  (4) QA  (5) Other")
    category_choice = read_line("Enter choice      : ")
    print("Proficiency Level : (1) Beginner  (2) Intermediate  (3) Advanced")
    proficiency_choice = read_line("Enter choice      : ")
    category = SKILL_CATEGORY_CHOICES.get(category_choice)
    proficiency = PROFICIENCY_CHOICES.get(proficiency_choice)
    if not skill_name or category is None or proficiency is None:
        print_error("Skill name, category, and proficiency are required.")
        pause()
        return skills
    try:
        client.add_user_skill(
            session.access_token,
            user_id,
            skill_name=skill_name,
            category=category,
            proficiency=proficiency,
        )
        skills = client.list_user_skills(session.access_token, user_id)
        print_success("Skill added. ✓")
    except ApiError as exc:
        print_error(str(exc))
    pause()
    return skills


def _update_skill_proficiency(client, session, user_id, skills):
    if not skills:
        print_error("No skills to update.")
        pause()
        return skills
    index = read_int("Enter skill # to update: ")
    if index is None or index < 1 or index > len(skills):
        print_error("Invalid skill number.")
        pause()
        return skills
    skill = skills[index - 1]
    print("Proficiency Level : (1) Beginner  (2) Intermediate  (3) Advanced")
    proficiency_choice = read_line("Enter choice      : ")
    proficiency = PROFICIENCY_CHOICES.get(proficiency_choice)
    if proficiency is None:
        print_error("Invalid proficiency choice.")
        pause()
        return skills
    try:
        client.update_user_skill(
            session.access_token,
            user_id,
            skill.user_skill_id,
            proficiency=proficiency,
        )
        skills = client.list_user_skills(session.access_token, user_id)
        print_success("Proficiency updated. ✓")
    except ApiError as exc:
        print_error(str(exc))
    pause()
    return skills


def _remove_skill(client, session, user_id, skills):
    if not skills:
        print_error("No skills to remove.")
        pause()
        return skills
    index = read_int("Enter skill # to remove: ")
    if index is None or index < 1 or index > len(skills):
        print_error("Invalid skill number.")
        pause()
        return skills
    skill = skills[index - 1]
    if not confirm_action(f"Remove skill '{skill.skill_name}'?"):
        return skills
    try:
        client.remove_user_skill(session.access_token, user_id, skill.user_skill_id)
        skills = client.list_user_skills(session.access_token, user_id)
        print_success("Skill removed. ✓")
    except ApiError as exc:
        print_error(str(exc))
    pause()
    return skills


def _assign_manager(client: PrmApiClient, session: UserSession) -> None:
    clear_screen()
    print_banner("ASSIGN MANAGER")
    engineer_user_id = read_int("Employee User ID : ")
    manager_user_id = read_int("Manager User ID  : ")
    if engineer_user_id is None or manager_user_id is None:
        pause()
        return
    print()
    print_divider()
    print("[S] Save     [B] Back")
    if read_save_or_back() is None:
        return
    try:
        updated = client.assign_manager(
            session.access_token,
            engineer_user_id=engineer_user_id,
            manager_user_id=manager_user_id,
        )
    except ApiError as exc:
        print_error(str(exc))
        pause()
        return
    print_success(f"Manager assigned to {updated.full_name}. ✓")
    pause()
