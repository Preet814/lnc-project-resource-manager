"""Manager panel placeholder until manager screens are implemented."""

from prm.console.session import UserSession
from prm.console.ui import (
    clear_screen,
    format_header_datetime,
    pause,
    print_banner,
    print_error,
    read_option,
)


def run(session: UserSession) -> str:
    while True:
        clear_screen()
        header = f"Welcome, {session.full_name}  |  {format_header_datetime()}"
        print_banner("MANAGER PANEL", subtitle=header)
        print("Manager features (allocations, timesheets, AI match) are coming")
        print("in the next console milestone.")
        print()
        print("1. Logout")
        print()
        choice = read_option()
        if choice == "1":
            return "logout"
        print_error("Invalid option. Choose 1 to logout.")
        pause()
