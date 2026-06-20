"""Forced password change screen (BRD Screen 1 — first login)."""

from prm.console.client import ApiError, PrmApiClient
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
)


def run(client: PrmApiClient, session: UserSession) -> None:
    while session.force_password_change:
        clear_screen()
        print_banner(
            "CHANGE PASSWORD",
            subtitle="You must set a new password to continue.",
        )
        new_password = read_password("New Password        : ")
        confirm_password = read_password("Confirm Password    : ")
        print()
        print_divider()
        print("[S] Save and Continue")
        print()
        action = read_line("Enter action [S] Save: ").strip().upper()
        if action not in {"S", "SAVE"}:
            print_error("Password change is required. Enter S to save.")
            pause()
            continue

        try:
            result = client.change_password(
                session.access_token,
                new_password=new_password,
                confirm_password=confirm_password,
            )
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
        print_success("Password updated. Welcome! ✓")
        pause()
