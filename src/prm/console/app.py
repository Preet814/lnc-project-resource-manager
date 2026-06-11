"""Console application orchestrator."""

import sys

from prm.console.client import ApiError, PrmApiClient
from prm.console.config import ConsoleConfig
from prm.console.screens import change_password, router, welcome
from prm.console.session import UserSession
from prm.console.ui import clear_screen, print_banner, print_success


def run(config: ConsoleConfig | None = None) -> None:
    settings = config or ConsoleConfig.from_env()
    session = UserSession.empty()

    with PrmApiClient(settings.api_base_url) as client:
        _wait_for_api(client, settings)
        _main_loop(client, session)

    clear_screen()
    print_success("Thank you for using PRM. Goodbye!")


def _wait_for_api(client: PrmApiClient, settings: ConsoleConfig) -> None:
    health_url = f"{settings.api_base_url.rstrip('/')}/health"
    print(f"PRM Console — waiting for API at {health_url}")
    try:
        body = client.wait_for_health(
            max_attempts=settings.max_health_attempts,
            retry_seconds=settings.health_retry_seconds,
        )
    except ApiError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
    print(f"API ready: {body}\n")


def _main_loop(client: PrmApiClient, session: UserSession) -> None:
    while True:
        if not session.is_authenticated:
            action = welcome.run(client, session)
            if action == "exit":
                return
            continue

        if session.force_password_change:
            change_password.run(client, session)
            continue

        if router.run_role_menu(client, session) == "logout":
            session.clear()
            clear_screen()
            print_banner("LOGGED OUT", subtitle="Returning to login screen.")
            print_success("You have been logged out.")
            continue


def main() -> None:
    run()
