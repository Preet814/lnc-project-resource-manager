"""Smoke tests for admin allocations view and system configuration against a running API."""

import pytest

from tests.integration.support import (
    admin_headers as _admin_headers,
    api_url as _api_url,
    request_or_skip as _request_or_skip,
)


@pytest.mark.integration
def test_admin_list_allocations_smoke() -> None:
    """Admin can list company-wide allocations (read-only)."""
    headers = _admin_headers()

    response = _request_or_skip("get", _api_url("/admin/allocations"), headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert "allocations" in body
    assert "total" in body
    assert body["total"] == len(body["allocations"])


@pytest.mark.integration
def test_admin_get_and_update_config_smoke() -> None:
    """Admin can read defaults and update system configuration settings."""
    headers = _admin_headers()

    current = _request_or_skip("get", _api_url("/admin/config"), headers=headers)
    assert current.status_code == 200
    defaults = current.json()
    assert defaults["llm_provider"] in {"GEMINI", "GROQ", "GEMMA"}
    assert defaults["scheduler_interval_hours"] >= 1
    assert defaults["max_weekly_hours"] >= 1

    update_key = _request_or_skip(
        "patch",
        _api_url("/admin/config/llm-api-key"),
        headers=headers,
        json={"api_key": "smoke-test-provider-key"},
    )
    assert update_key.status_code == 200
    assert update_key.json()["llm_api_key_masked"] is not None

    update_provider = _request_or_skip(
        "patch",
        _api_url("/admin/config/llm-provider"),
        headers=headers,
        json={"provider": "GROQ"},
    )
    assert update_provider.status_code == 200
    assert update_provider.json()["llm_provider"] == "GROQ"

    update_interval = _request_or_skip(
        "patch",
        _api_url("/admin/config/scheduler-interval"),
        headers=headers,
        json={"scheduler_interval_hours": 6},
    )
    assert update_interval.status_code == 200
    assert update_interval.json()["scheduler_interval_hours"] == 6

    update_hours = _request_or_skip(
        "patch",
        _api_url("/admin/config/max-weekly-hours"),
        headers=headers,
        json={"max_weekly_hours": 35},
    )
    assert update_hours.status_code == 200
    assert update_hours.json()["max_weekly_hours"] == 35

    final = _request_or_skip("get", _api_url("/admin/config"), headers=headers)
    assert final.status_code == 200
    body = final.json()
    assert body["llm_provider"] == "GROQ"
    assert body["scheduler_interval_hours"] == 6
    assert body["max_weekly_hours"] == 35
    assert body["llm_api_key_masked"] is not None
