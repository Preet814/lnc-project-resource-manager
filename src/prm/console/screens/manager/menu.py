"""Screen 4 — Manager panel."""

from prm.console.client import PrmApiClient
from prm.console.screens.manager import (
    ai_assistant,
    allocate_resource,
    my_projects,
    resource_dashboard,
    timesheets,
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
    """Run manager menu until logout. Returns 'logout'."""
    while True:
        clear_screen()
        header = f"Welcome, {session.full_name}!  |  {format_header_datetime()}"
        print_banner("MANAGER PANEL", subtitle=header)
        print("1. Resource Dashboard")
        print("2. Allocate Resource")
        print("3. My Projects")
        print("4. Timesheets")
        print("5. AI Assistant")
        print("6. Logout")
        print()
        choice = read_option()

        if choice == "6":
            return "logout"
        if choice == "1":
            resource_dashboard.run(client, session)
        elif choice == "2":
            allocate_resource.run(client, session)
        elif choice == "3":
            my_projects.run(client, session)
        elif choice == "4":
            timesheets.run(client, session)
        elif choice == "5":
            ai_assistant.run(client, session)
        else:
            print_error("Invalid option. Choose 1–6.")
            pause()
