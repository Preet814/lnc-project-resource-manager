"""SQLAlchemy column type helpers for ORM models."""

from sqlalchemy import Enum

from prm.domain.enums import (
    ActivityTag,
    AllocationStatus,
    LLMProvider,
    MilestoneStatus,
    ProficiencyLevel,
    ProjectHealthStatus,
    ProjectStatus,
    ResourceWorkStatus,
    Role,
    SkillCategory,
    TimesheetWeekStatus,
    UserAccountStatus,
)

user_account_status_enum = Enum(
    UserAccountStatus, name="user_account_status", native_enum=False, length=20
)
resource_work_status_enum = Enum(
    ResourceWorkStatus, name="resource_work_status", native_enum=False, length=20
)
skill_category_enum = Enum(SkillCategory, name="skill_category", native_enum=False, length=20)
proficiency_level_enum = Enum(
    ProficiencyLevel, name="proficiency_level", native_enum=False, length=20
)
project_status_enum = Enum(ProjectStatus, name="project_status", native_enum=False, length=20)
project_health_status_enum = Enum(
    ProjectHealthStatus, name="project_health_status", native_enum=False, length=20
)
milestone_status_enum = Enum(
    MilestoneStatus, name="milestone_status", native_enum=False, length=20
)
allocation_status_enum = Enum(
    AllocationStatus, name="allocation_status", native_enum=False, length=20
)
timesheet_week_status_enum = Enum(
    TimesheetWeekStatus, name="timesheet_week_status", native_enum=False, length=20
)
llm_provider_enum = Enum(LLMProvider, name="llm_provider", native_enum=False, length=20)
activity_tag_enum = Enum(ActivityTag, name="activity_tag", native_enum=False, length=30)

# Legacy — removed from users table; Role enum used in application layer only
role_enum = Enum(Role, name="role", native_enum=False, length=20)
