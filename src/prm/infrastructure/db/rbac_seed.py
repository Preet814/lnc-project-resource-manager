"""RBAC lookup seed data for roles, permissions, and default role_permissions."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from prm.domain.constants import SEEDED_DEPARTMENTS, SEEDED_DESIGNATIONS
from prm.domain.permission_codes import (
    ALLOCATION_CREATE,
    ALLOCATION_END,
    ALLOCATION_VIEW_ALL,
    ALLOCATION_VIEW_OWN,
    CONFIG_MANAGE,
    ENGINEER_ASSIGN_MANAGER,
    ENGINEER_MANAGE,
    LLM_RISK_SUMMARY,
    LLM_SKILL_MATCH,
    MILESTONE_MANAGE,
    PROJECT_CREATE,
    PROJECT_HEALTH_VIEW,
    RESOURCE_SEARCH_AI,
    RESOURCE_VIEW_DASHBOARD,
    ROLE_MANAGE,
    SKILL_MANAGE_ANY,
    TIMESHEET_SUBMIT,
    TIMESHEET_VIEW_OWN,
    TIMESHEET_VIEW_TEAM,
    USER_CREATE,
    USER_DEACTIVATE,
    USER_RESET_PASSWORD,
)
from prm.infrastructure.db.models.department import DepartmentModel
from prm.infrastructure.db.models.designation import DesignationModel
from prm.infrastructure.db.models.permission import PermissionModel, RolePermissionModel
from prm.infrastructure.db.models.role import RoleModel

ROLES = (
    (1, "ENGINEER", "Engineer", 1),
    (2, "MANAGER", "Manager", 2),
    (3, "ADMIN", "Admin", 3),
)

DEPARTMENTS = SEEDED_DEPARTMENTS
DESIGNATIONS = SEEDED_DESIGNATIONS

PERMISSIONS = (
    (TIMESHEET_SUBMIT, "Submit timesheet", 1, "TIMESHEET"),
    (TIMESHEET_VIEW_OWN, "View own timesheets", 1, "TIMESHEET"),
    (ALLOCATION_VIEW_OWN, "View own allocations", 1, "ALLOCATION"),
    (RESOURCE_SEARCH_AI, "AI resource search", 2, "RESOURCE"),
    (ALLOCATION_CREATE, "Create allocation", 2, "ALLOCATION"),
    (ALLOCATION_END, "End allocation", 2, "ALLOCATION"),
    (PROJECT_HEALTH_VIEW, "View project health", 2, "PROJECT"),
    (TIMESHEET_VIEW_TEAM, "View team timesheets", 2, "TIMESHEET"),
    (LLM_SKILL_MATCH, "LLM skill match", 2, "LLM"),
    (LLM_RISK_SUMMARY, "LLM risk summary", 2, "LLM"),
    (RESOURCE_VIEW_DASHBOARD, "Resource dashboard", 2, "RESOURCE"),
    (USER_CREATE, "Create user", 3, "USER"),
    (USER_DEACTIVATE, "Deactivate user", 3, "USER"),
    (USER_RESET_PASSWORD, "Reset password", 3, "USER"),
    (ENGINEER_MANAGE, "Manage engineers", 3, "ENGINEER"),
    (ENGINEER_ASSIGN_MANAGER, "Assign manager", 3, "ENGINEER"),
    (SKILL_MANAGE_ANY, "Manage any user skills", 3, "SKILL"),
    (PROJECT_CREATE, "Create project", 3, "PROJECT"),
    (MILESTONE_MANAGE, "Manage milestones", 3, "PROJECT"),
    (ALLOCATION_VIEW_ALL, "View all allocations", 3, "ALLOCATION"),
    (CONFIG_MANAGE, "Manage system config", 3, "CONFIG"),
    (ROLE_MANAGE, "Manage roles and permissions", 3, "RBAC"),
)

ROLE_PERMISSION_MAP: dict[str, tuple[str, ...]] = {
    "ENGINEER": (
        TIMESHEET_SUBMIT,
        TIMESHEET_VIEW_OWN,
        ALLOCATION_VIEW_OWN,
    ),
    "MANAGER": (
        RESOURCE_SEARCH_AI,
        ALLOCATION_CREATE,
        ALLOCATION_END,
        PROJECT_HEALTH_VIEW,
        TIMESHEET_VIEW_TEAM,
        LLM_SKILL_MATCH,
        LLM_RISK_SUMMARY,
        RESOURCE_VIEW_DASHBOARD,
    ),
    "ADMIN": (
        USER_CREATE,
        USER_DEACTIVATE,
        USER_RESET_PASSWORD,
        ENGINEER_MANAGE,
        ENGINEER_ASSIGN_MANAGER,
        SKILL_MANAGE_ANY,
        PROJECT_CREATE,
        MILESTONE_MANAGE,
        ALLOCATION_VIEW_ALL,
        CONFIG_MANAGE,
        ROLE_MANAGE,
    ),
}


def seed_rbac_lookups(session: Session) -> None:
    """Insert roles, permissions, departments, designations, and default grants if missing."""
    for role_id, code, name, rank in ROLES:
        if session.get(RoleModel, role_id) is None:
            session.add(
                RoleModel(
                    id=role_id,
                    code=code,
                    name=name,
                    hierarchy_rank=rank,
                    is_system=True,
                )
            )

    for code, name, level, module in PERMISSIONS:
        existing = session.scalar(
            select(PermissionModel).where(PermissionModel.code == code)
        )
        if existing is None:
            session.add(
                PermissionModel(
                    code=code,
                    name=name,
                    hierarchy_level=level,
                    module=module,
                )
            )

    session.flush()

    for dept_name in DEPARTMENTS:
        existing = session.scalar(
            select(DepartmentModel).where(DepartmentModel.name == dept_name)
        )
        if existing is None:
            session.add(DepartmentModel(name=dept_name))

    for des_name, track in DESIGNATIONS:
        existing = session.scalar(
            select(DesignationModel).where(DesignationModel.name == des_name)
        )
        if existing is None:
            session.add(DesignationModel(name=des_name, track=track))

    session.flush()

    permission_by_code = {
        row.code: row
        for row in session.scalars(select(PermissionModel)).all()
    }
    role_by_code = {row.code: row for row in session.scalars(select(RoleModel)).all()}

    for role_code, perm_codes in ROLE_PERMISSION_MAP.items():
        role = role_by_code[role_code]
        for perm_code in perm_codes:
            permission = permission_by_code[perm_code]
            if permission.hierarchy_level > role.hierarchy_rank:
                continue
            exists = session.scalar(
                select(RolePermissionModel).where(
                    RolePermissionModel.role_id == role.id,
                    RolePermissionModel.permission_id == permission.id,
                )
            )
            if exists is None:
                session.add(
                    RolePermissionModel(role_id=role.id, permission_id=permission.id)
                )

    session.flush()


def default_department_id(session: Session, *, name: str = "IT") -> int:
    dept = session.scalar(select(DepartmentModel).where(DepartmentModel.name == name))
    if dept is None:
        raise RuntimeError(f"Department '{name}' not seeded.")
    return dept.id


def default_designation_id(session: Session, *, name: str = "System Administrator") -> int:
    designation = session.scalar(
        select(DesignationModel).where(DesignationModel.name == name)
    )
    if designation is None:
        raise RuntimeError(f"Designation '{name}' not seeded.")
    return designation.id


def role_id_for_code(session: Session, code: str) -> int:
    role = session.scalar(select(RoleModel).where(RoleModel.code == code))
    if role is None:
        raise RuntimeError(f"Role '{code}' not seeded.")
    return role.id
