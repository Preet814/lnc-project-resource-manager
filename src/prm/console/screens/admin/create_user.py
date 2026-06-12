"""Screen 3.4.1 — Create user account (admin only)."""

from prm.console.client import ApiError, PrmApiClient
from prm.console.screens.admin._helpers import display_value, read_optional_numbered_choice
from prm.console.ui.choices import DEPARTMENT_CHOICES, DESIGNATION_CHOICES
from prm.console.session import UserSession
from prm.console.ui import (
    clear_screen,
    pause,
    print_banner,
    print_divider,
    print_error,
    print_success,
    read_line,
    read_password,
    read_save_or_back,
)
from prm.domain.enums import Role

_ROLE_CHOICES: dict[str, Role] = {
    "1": Role.ADMIN,
    "2": Role.MANAGER,
    "3": Role.ENGINEER,
}


def run(client: PrmApiClient, session: UserSession) -> None:
    while True:
        clear_screen()
        print_banner("CREATE USER ACCOUNT")
        full_name = read_line("Full Name         : ")
        email = read_line("Email             : ")
        username = read_line("Username          : ")
        temporary_password = read_password("Temporary Password: ")
        print("Role              : (1) Admin  (2) Manager  (3) Engineer")
        role_choice = read_line("Select role [1-3]: ")
        department = read_optional_numbered_choice(
            DEPARTMENT_CHOICES,
            label="(optional) Department",
        )
        designation = read_optional_numbered_choice(
            DESIGNATION_CHOICES,
            label="(optional) Designation",
        )
        print()
        print_divider()
        print("[S] Save     [B] Back")
        print()

        action = read_save_or_back()
        if action is None:
            return

        role = _ROLE_CHOICES.get(role_choice)
        if not all([full_name, email, username, temporary_password]):
            print_error("All fields are mandatory.")
            pause()
            continue
        if role is None:
            print_error("Role must be 1 (Admin), 2 (Manager), or 3 (Engineer).")
            pause()
            continue

        try:
            created = client.create_user(
                session.access_token,
                full_name=full_name,
                email=email,
                username=username,
                temporary_password=temporary_password,
                role=role,
                department=department,
                designation=designation,
            )
        except ApiError as exc:
            print_error(str(exc))
            pause()
            continue

        print_success(
            "Account created. User must change password on first login. ✓\n"
            f"  ID: {created.id}  |  Username: {created.username}  |  Role: {created.role.value}\n"
            f"  Department: {display_value(department)}  |  "
            f"Designation: {display_value(designation)}"
        )
        pause()
        return
