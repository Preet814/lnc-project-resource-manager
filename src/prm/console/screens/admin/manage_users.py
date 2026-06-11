"""Screen 3.4 — Manage users."""

from prm.console.client import ApiError, PrmApiClient
from prm.console.screens.admin import create_user
from prm.console.screens.admin._helpers import (
    confirm_action,
    read_user_identifier,
    resolve_user,
    role_label,
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
    read_password,
    read_save_or_back,
)
from prm.domain.enums import UserAccountStatus


def run(client: PrmApiClient, session: UserSession) -> None:
    while True:
        clear_screen()
        print_banner("MANAGE USERS")
        print("1. Create User Account")
        print("2. View All Users")
        print("3. Reset User Password")
        print("4. Deactivate User")
        print("5. Back")
        print()
        choice = read_option()

        if choice == "5":
            return
        if choice == "1":
            create_user.run(client, session)
        elif choice == "2":
            _view_all_users(client, session)
        elif choice == "3":
            _reset_password(client, session)
        elif choice == "4":
            _deactivate_user(client, session)
        else:
            print_error("Invalid option. Choose 1–5.")
            pause()


def _view_all_users(client: PrmApiClient, session: UserSession) -> None:
    while True:
        clear_screen()
        print_banner("ALL USERS")
        try:
            result = client.list_users(session.access_token)
        except ApiError as exc:
            print_error(str(exc))
            pause()
            return

        print(f"{'ID':<5}{'Username':<18}{'Role':<12}{'Status'}")
        print_divider(52)
        for user in result.users:
            status = "Active" if user.account_status == UserAccountStatus.ACTIVE else "Inactive"
            print(f"{user.id:<5}{user.username:<18}{role_label(user.role):<12}{status}")
        print_divider(52)
        print(
            f"Total: {result.total}   |   Active: {result.active_count}   |   "
            f"Inactive: {result.inactive_count}"
        )
        print()
        print("[R] Reactivate a user     [B] Back")
        action = read_line("Enter action: ").strip().upper()
        if action in {"B", "BACK"}:
            return
        if action in {"R", "REACTIVATE"}:
            _reactivate_user(client, session)
            continue
        print_error("Enter R to reactivate or B to go back.")
        pause()


def _reactivate_user(client: PrmApiClient, session: UserSession) -> None:
    user_id = read_line("Enter User ID to reactivate: ").strip()
    if not user_id.isdigit():
        print_error("Please enter a valid user ID.")
        pause()
        return

    user = resolve_user(client, session, user_id)
    if user is None:
        print_error(f"User {user_id} not found.")
        pause()
        return
    if user.account_status == UserAccountStatus.ACTIVE:
        print_error(f"User '{user.username}' is already active.")
        pause()
        return

    status = "Inactive"
    print(f"\nUser: {user.full_name} ({role_label(user.role)}) — currently {status}")
    if not confirm_action("Reactivate this account?"):
        return

    try:
        client.reactivate_user(session.access_token, user.id)
    except ApiError as exc:
        print_error(str(exc))
        pause()
        return

    print_success(
        f"Account reactivated. {user.full_name} can now log in. ✓\n"
        "Note: Previous allocations are NOT restored. Admin must re-allocate manually if needed."
    )
    pause()


def _reset_password(client: PrmApiClient, session: UserSession) -> None:
    clear_screen()
    print_banner("RESET USER PASSWORD")
    identifier = read_user_identifier()
    user = resolve_user(client, session, identifier)
    if user is not None:
        print(f"\nUser found: {user.full_name} ({role_label(user.role)})")
    temporary_password = read_password("\nNew Temporary Password: ")
    print()
    print_divider()
    print("[S] Save     [B] Back")
    if read_save_or_back() is None:
        return
    if not temporary_password:
        print_error("Temporary password is required.")
        pause()
        return

    try:
        client.reset_user_password(
            session.access_token,
            identifier=identifier,
            temporary_password=temporary_password,
        )
    except ApiError as exc:
        print_error(str(exc))
        pause()
        return

    print_success("Password reset. User will be prompted to change it on next login. ✓")
    pause()


def _deactivate_user(client: PrmApiClient, session: UserSession) -> None:
    clear_screen()
    print_banner("DEACTIVATE USER")
    identifier = read_user_identifier()
    user = resolve_user(client, session, identifier)
    if user is None:
        print_error(f"User '{identifier}' not found.")
        pause()
        return
    if user.id == session.user_id:
        print_error("You cannot deactivate your own account.")
        pause()
        return

    status = "Active" if user.account_status == UserAccountStatus.ACTIVE else "Inactive"
    print(f"\nUser found: {user.full_name} ({role_label(user.role)})")
    print(f"Status     : {status}")
    if user.account_status != UserAccountStatus.ACTIVE:
        print_error("User is already inactive.")
        pause()
        return

    if not confirm_action(
        "Are you sure you want to deactivate this account?\n"
        "Deactivated users cannot log in. Their data is preserved."
    ):
        return

    try:
        client.deactivate_user(session.access_token, user.id)
    except ApiError as exc:
        print_error(str(exc))
        pause()
        return

    print_success("User deactivated. ✓")
    pause()
