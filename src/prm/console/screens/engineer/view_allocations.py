"""Screen 5.3 — View my allocations."""

from prm.console.client import ApiError, PrmApiClient
from prm.console.session import UserSession
from prm.console.ui import (
    clear_screen,
    pause,
    print_banner,
    print_divider,
    print_error,
)
from prm.console.ui.dates import format_date


def run(client: PrmApiClient, session: UserSession) -> None:
    clear_screen()
    print_banner("MY ALLOCATIONS")
    try:
        result = client.list_my_allocations(session.access_token)
    except ApiError as exc:
        print_error(str(exc))
        pause()
        return

    print(f"{'Project':<18}{'%':<7}{'From':<12}{'To':<12}{'Status'}")
    print_divider(62)
    if result.allocations:
        for allocation in result.allocations:
            print(
                f"{allocation.project_name:<18}"
                f"{allocation.utilisation_percent}%{'':<4}"
                f"{format_date(allocation.from_date):<12}"
                f"{format_date(allocation.to_date):<12}"
                f"{allocation.status.value}"
            )
    else:
        print("(no allocations)")
    print_divider(62)
    print(f"Total Utilisation: {result.total_utilisation_percent}%")
    print()
    print("[B] Back")
    pause()
