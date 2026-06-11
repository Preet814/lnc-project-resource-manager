"""Block until PostgreSQL accepts TCP connections (Docker DNS/startup race)."""

from __future__ import annotations

import os
import sys
import time
from urllib.parse import urlparse

import psycopg2

DEFAULT_ATTEMPTS = 30
RETRY_SECONDS = 2


def wait_for_postgres(
    database_url: str,
    *,
    max_attempts: int = DEFAULT_ATTEMPTS,
    retry_seconds: float = RETRY_SECONDS,
) -> None:
    parsed = urlparse(database_url)
    host = parsed.hostname or "postgres"
    port = parsed.port or 5432
    user = parsed.username or "prm"
    password = parsed.password or "prm"
    dbname = (parsed.path or "/prm").lstrip("/") or "prm"

    for attempt in range(1, max_attempts + 1):
        try:
            conn = psycopg2.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                dbname=dbname,
                connect_timeout=3,
            )
            conn.close()
            print(f"PostgreSQL ready at {host}:{port} (attempt {attempt}).")
            return
        except psycopg2.OperationalError as exc:
            print(f"Waiting for PostgreSQL ({attempt}/{max_attempts}): {exc}")
            time.sleep(retry_seconds)

    print("PostgreSQL did not become reachable in time.", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    database_url = os.environ.get(
        "DATABASE_URL",
        "postgresql://prm:prm@postgres:5432/prm",
    )
    wait_for_postgres(database_url)


if __name__ == "__main__":
    main()
