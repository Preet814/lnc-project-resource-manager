"""Unit tests for ORM model metadata."""

import prm.infrastructure.db.models  # noqa: F401 — register metadata
from prm.infrastructure.db.base import Base


def test_metadata_registers_all_entity_tables() -> None:
    expected = {
        "users",
        "roles",
        "permissions",
        "role_permissions",
        "departments",
        "designations",
        "resource_status",
        "skills",
        "user_skills",
        "projects",
        "milestones",
        "project_health_snapshots",
        "allocations",
        "timesheet_weeks",
        "timesheet_entries",
        "system_configurations",
    }
    assert expected.issubset(set(Base.metadata.tables.keys()))


def test_user_table_has_force_password_change_column() -> None:
    users = Base.metadata.tables["users"]
    assert "force_password_change" in users.c
    assert users.c.username.unique is True
