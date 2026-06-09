"""Unit tests for the health endpoint."""

import os

from fastapi.testclient import TestClient

from prm.api.app import create_app
from prm.api.settings import get_settings


def test_health_returns_ok() -> None:
    os.environ["SCHEDULER_ENABLED"] = "false"
    get_settings.cache_clear()
    client = TestClient(create_app())
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "PRM API"
    assert body["version"] == "0.1.0"
