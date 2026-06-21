"""Forced email verification screen (first login after password change)."""

from prm.console.client import ApiError, PrmApiClient
from prm.console.session import UserSession
from prm.console.ui import (
    clear_screen,
    pause,
    print_banner,
    print_error,
    print_success,
    read_line,
)


def _read_verify_action() -> str:
    while True:
        action = read_line("Enter action [S] Send / [C] Confirm / [B] Back to login: ").strip().upper()
        if action in {"S", "SEND"}:
            return "S"
        if action in {"C", "CONFIRM"}:
            return "C"
        if action in {"B", "BACK"}:
            return "B"
        print_error("Please enter S to send code, C to confirm, or B to go back.")


def run(client: PrmApiClient, session: UserSession) -> str | None:
    """Verify email via OTP. Returns ``logout`` when user chooses to return to login."""
    while not session.email_verified:
        clear_screen()
        print_banner(
            "VERIFY EMAIL",
            subtitle="Enter the one-time code sent to your registered email address.",
        )
        print(f"Account: {session.full_name} ({session.username})")
        print()
        print("[S] Send / resend code")
        print("[C] Confirm code")
        print("[B] Back to login")
        print()
        action = _read_verify_action()

        if action == "B":
            session.clear()
            return "logout"

        if action == "S":
            try:
                client.send_email_verification_otp(session.access_token)
            except ApiError as exc:
                print_error(str(exc))
                pause()
                continue
            print_success("Verification code sent. Check your email.")
            pause()
            continue

        # action == "C"
        otp = read_line("Enter verification code: ").strip()
        if not otp:
            print_error("Verification code is required.")
            pause()
            continue

        try:
            result = client.confirm_email_verification_otp(session.access_token, otp=otp)
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
        print_success("Email verified successfully. ✓")
        pause()
    return None
