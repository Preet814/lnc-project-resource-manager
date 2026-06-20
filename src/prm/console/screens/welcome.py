"""Screen 1 — Application start and login."""

from prm.console.client import ApiError, PrmApiClient
from prm.console.session import UserSession
from prm.console.ui import (
    clear_screen,
    pause,
    print_banner,
    print_error,
    print_success,
    read_line,
    read_option,
    read_password,
)


def run(client: PrmApiClient, session: UserSession) -> str:
    """Show login menu. Returns 'exit' or 'continue' after successful login."""
    while True:
        clear_screen()
        print_banner(
            "PROJECT & RESOURCE MANAGEMENT TOOL",
            subtitle="Learn & Code — Final Project",
        )
        print("1. Login")
        print("2. Exit")
        print()
        choice = read_option()

        if choice == "2":
            return "exit"
        if choice != "1":
            print_error("Invalid option. Choose 1 or 2.")
            pause()
            continue

        username = read_line("Username: ")
        password = read_password("Password: ")
        if not username or not password:
            print_error("Username and password are required.")
            pause()
            continue

        try:
            result = client.login(username, password)
        except ApiError as exc:
            print_error(str(exc))
            pause()
            continue

        session.apply_login(
            access_token=result.access_token,
            user_id=result.user_id,
            username=result.username,
            full_name=result.full_name,
            role=result.role,
            force_password_change=result.force_password_change,
            email_verified=result.email_verified,
        )
        if result.force_password_change:
            print_success("Login successful. You must change your password to continue.")
        elif not result.email_verified:
            print_success("Login successful. Verify your email address to continue.")
        else:
            print_success(f"Welcome, {result.full_name}!")
        pause()
        return "continue"
