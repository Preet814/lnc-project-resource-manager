"""Stable permission code constants for RBAC checks."""

# Level 1 — Engineer
TIMESHEET_SUBMIT = "timesheet:submit"
TIMESHEET_VIEW_OWN = "timesheet:view_own"
ALLOCATION_VIEW_OWN = "allocation:view_own"

# Level 2 — Manager
RESOURCE_SEARCH_AI = "resource:search_ai"
ALLOCATION_CREATE = "allocation:create"
ALLOCATION_END = "allocation:end"
PROJECT_HEALTH_VIEW = "project:health_view"
TIMESHEET_VIEW_TEAM = "timesheet:view_team"
LLM_SKILL_MATCH = "llm:skill_match"
LLM_RISK_SUMMARY = "llm:risk_summary"
RESOURCE_VIEW_DASHBOARD = "resource:view_dashboard"

# Level 3 — Admin
USER_CREATE = "user:create"
USER_DEACTIVATE = "user:deactivate"
USER_RESET_PASSWORD = "user:reset_password"
ENGINEER_MANAGE = "engineer:manage"
ENGINEER_ASSIGN_MANAGER = "engineer:assign_manager"
SKILL_MANAGE_ANY = "skill:manage_any"
PROJECT_CREATE = "project:create"
MILESTONE_MANAGE = "milestone:manage"
ALLOCATION_VIEW_ALL = "allocation:view_all"
CONFIG_MANAGE = "config:manage"
ROLE_MANAGE = "role:manage"
