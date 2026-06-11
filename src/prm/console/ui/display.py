"""Console presentation helpers (BRD-style banners and messages)."""

from datetime import datetime


def clear_screen() -> None:
    print("\n" * 2)


def print_banner(title: str, *, subtitle: str | None = None, width: int = 46) -> None:
    inner_width = width - 2
    top = "╔" + "═" * inner_width + "╗"
    bottom = "╚" + "═" * inner_width + "╝"
    print(top)
    print(f"║{title.center(inner_width)}║")
    if subtitle:
        print(f"║{subtitle.center(inner_width)}║")
    print(bottom)
    print()


def print_divider(width: int = 46) -> None:
    print("─" * width)


def print_success(message: str) -> None:
    print(f"\n{message}")


def print_error(message: str) -> None:
    print(f"\nError: {message}")


def format_header_datetime() -> str:
    return datetime.now().strftime("%d-%m-%Y  %H:%M")


def pause(message: str = "Press Enter to continue...") -> None:
    input(message)
