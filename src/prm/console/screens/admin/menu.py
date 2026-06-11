"""Screen 3 — Admin panel."""

from prm.console.client import PrmApiClient
from prm.console.screens.admin import (
    manage_employees,
    manage_projects,
    manage_users,
    system_config,
    view_allocations,
)
from prm.console.session import UserSession
from prm.console.ui import (
    clear_screen,
    format_header_datetime,
    pause,
    print_banner,
    print_error,
    read_option,
)


def run(client: PrmApiClient, session: UserSession) -> str:
    """Run admin menu until logout. Returns 'logout'."""
    while True:
        clear_screen()
        header = f"Welcome, {session.full_name}  |  {format_header_datetime()}"
        print_banner("ADMIN PANEL", subtitle=header)
        print("1. Manage Employees")
        print("2. Manage Projects")
        print("3. View All Allocations")
        print("4. Manage Users")
        print("5. System Configuration")
        print("6. Logout")
        print()
        choice = read_option()

        if choice == "6":
            return "logout"
        if choice == "1":
            manage_employees.run(client, session)
        elif choice == "2":
            manage_projects.run(client, session)
        elif choice == "3":
            view_allocations.run(client, session)
        elif choice == "4":
            manage_users.run(client, session)
        elif choice == "5":
            system_config.run(client, session)
        else:
            print_error("Invalid option. Choose 1–6.")
            pause()
