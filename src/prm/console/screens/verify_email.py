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
    read_save_or_back,
)


def run(client: PrmApiClient, session: UserSession) -> None:
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
        print("[B] Back (logout required to switch user)")
        print()
        action = read_save_or_back().strip().upper()

        if action == "B":
            print_error("Complete email verification to continue.")
            pause()
            continue

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

        if action != "C":
            print_error("Choose S to send code or C to confirm.")
            pause()
            continue

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
