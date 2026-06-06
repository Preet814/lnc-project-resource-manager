"""Smoke test against a running API (Docker or local server)."""

import os

import httpx
import pytest

API_BASE_URL = os.getenv("PRM_API_URL", "http://localhost:8000")


@pytest.mark.integration
def test_health_endpoint_smoke() -> None:
    """Requires API reachable at PRM_API_URL (default http://localhost:8000)."""
    health_url = f"{API_BASE_URL.rstrip('/')}/health"

    try:
        response = httpx.get(health_url, timeout=5.0)
    except httpx.ConnectError as exc:
        pytest.skip(f"API not running at {health_url}: {exc}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "PRM API"
    assert "version" in body
