"""Screen 3.5 — System configuration."""

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
    read_option,
    read_password,
)
from prm.console.ui.choices import LLM_PROVIDER_CHOICES
from prm.domain.enums import LLMProvider


def _provider_label(provider: LLMProvider) -> str:
    if provider == LLMProvider.GEMINI:
        return "Google Gemini"
    if provider == LLMProvider.GROQ:
        return "Groq"
    return "Gemma (self-hosted)"


def run(client: PrmApiClient, session: UserSession) -> None:
    while True:
        clear_screen()
        print_banner("SYSTEM CONFIGURATION")
        try:
            config = client.get_configuration(session.access_token)
        except ApiError as exc:
            print_error(str(exc))
            pause()
            return

        masked_key = config.llm_api_key_masked or "(not set)"
        print("Current Settings:")
        print(f"  LLM Provider        :  {_provider_label(config.llm_provider)}")
        print(f"  LLM API Key         :  {masked_key}")
        print(f"  Scheduler Interval  :  {config.scheduler_interval_hours} hours")
        print(f"  Max Weekly Hours    :  {config.max_weekly_hours}")
        print()
        print_divider()
        print("1. Update LLM API Key")
        print("2. Change LLM Provider  (Gemini / Groq/ Gemma (self-hosted))")
        print("3. Update Scheduler Interval")
        print("4. Update Max Weekly Hours")
        print("5. Back")
        print()
        choice = read_option()

        if choice == "5":
            return
        if choice == "1":
            _update_api_key(client, session)
        elif choice == "2":
            _update_provider(client, session)
        elif choice == "3":
            _update_scheduler_interval(client, session)
        elif choice == "4":
            _update_max_weekly_hours(client, session)
        else:
            print_error("Invalid option. Choose 1–5.")
            pause()


def _update_api_key(client: PrmApiClient, session: UserSession) -> None:
    api_key = read_password("New LLM API Key: ")
    if not api_key:
        print_error("API key cannot be empty.")
        pause()
        return
    try:
        client.update_llm_api_key(session.access_token, api_key)
    except ApiError as exc:
        print_error(str(exc))
        pause()
        return
    print_success("LLM API key updated. ✓")
    pause()


def _update_provider(client: PrmApiClient, session: UserSession) -> None:
    print("Select provider: (1) Gemini   (2) Groq   (3) Gemma (self-hosted)")
    choice = read_line("Enter choice: ").strip()
    provider = LLM_PROVIDER_CHOICES.get(choice)
    if provider is None:
        print_error("Invalid provider choice.")
        pause()
        return
    try:
        client.update_llm_provider(session.access_token, provider)
    except ApiError as exc:
        print_error(str(exc))
        pause()
        return
    print_success(f"LLM provider changed to {_provider_label(provider)}. ✓")
    pause()


def _update_scheduler_interval(client: PrmApiClient, session: UserSession) -> None:
    raw = read_line("Scheduler interval (hours, 1–168): ").strip()
    if not raw.isdigit():
        print_error("Enter a valid number of hours.")
        pause()
        return
    try:
        client.update_scheduler_interval(session.access_token, int(raw))
    except ApiError as exc:
        print_error(str(exc))
        pause()
        return
    print_success("Scheduler interval updated. ✓")
    pause()


def _update_max_weekly_hours(client: PrmApiClient, session: UserSession) -> None:
    raw = read_line("Max weekly hours (1–168): ").strip()
    if not raw.isdigit():
        print_error("Enter a valid number of hours.")
        pause()
        return
    try:
        client.update_max_weekly_hours(session.access_token, int(raw))
    except ApiError as exc:
        print_error(str(exc))
        pause()
        return
    print_success("Max weekly hours updated. ✓")
    pause()
