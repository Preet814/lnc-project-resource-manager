"""Unit tests for domain enumerations."""

from prm.domain.enums import (
    ActivityTag,
    AllocationStatus,
    EmployeeWorkStatus,
    LLMProvider,
    MilestoneStatus,
    ProficiencyLevel,
    ProjectHealthStatus,
    ProjectStatus,
    Role,
    SkillCategory,
    TimesheetWeekStatus,
    UserAccountStatus,
)


def test_role_values() -> None:
    assert set(Role) == {Role.ADMIN, Role.MANAGER, Role.EMPLOYEE}


def test_user_account_status_values() -> None:
    assert set(UserAccountStatus) == {UserAccountStatus.ACTIVE, UserAccountStatus.INACTIVE}


def test_project_status_includes_completed() -> None:
    values = {status.value for status in ProjectStatus}
    assert values == {"PLANNED", "ACTIVE", "ON_HOLD", "COMPLETED"}


def test_activity_tag_is_string_enum() -> None:
    assert ActivityTag.BACKEND_API == "BACKEND_API"
    assert isinstance(ActivityTag.FRONTEND, str)


def test_all_enums_are_str_enums() -> None:
    enums = [
        Role,
        UserAccountStatus,
        EmployeeWorkStatus,
        SkillCategory,
        ProficiencyLevel,
        ProjectStatus,
        ProjectHealthStatus,
        MilestoneStatus,
        AllocationStatus,
        TimesheetWeekStatus,
        LLMProvider,
        ActivityTag,
    ]
    for enum_cls in enums:
        for member in enum_cls:
            assert isinstance(member, str)
