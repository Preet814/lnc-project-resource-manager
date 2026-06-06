"""Console client entry point (stub until Phase 5 menus)."""

import os
import sys
import time

import httpx

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
MAX_ATTEMPTS = 30
RETRY_SECONDS = 2


def wait_for_api() -> dict[str, str]:
    health_url = f"{API_BASE_URL.rstrip('/')}/health"
    print(f"PRM Console (stub) — waiting for API at {health_url}")

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = httpx.get(health_url, timeout=5.0)
            if response.status_code == 200:
                body: dict[str, str] = response.json()
                print(f"API ready (attempt {attempt}): {body}")
                return body
        except httpx.HTTPError as exc:
            print(f"Attempt {attempt}/{MAX_ATTEMPTS}: API not ready ({exc})")
        time.sleep(RETRY_SECONDS)

    print("API did not become reachable in time.", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    wait_for_api()
    print("Console menus will be implemented in Phase 5. Press Ctrl+C to exit.")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print("Console stub stopped.")


if __name__ == "__main__":
    main()
