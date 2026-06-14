"""ORM model registry — import all models so Alembic sees metadata."""

from prm.infrastructure.db.models.allocation import AllocationModel
from prm.infrastructure.db.models.department import DepartmentModel
from prm.infrastructure.db.models.designation import DesignationModel
from prm.infrastructure.db.models.permission import PermissionModel, RolePermissionModel
from prm.infrastructure.db.models.email_verification_otp import EmailVerificationOtpModel
from prm.infrastructure.db.models.project import (
    MilestoneModel,
    ProjectHealthSnapshotModel,
    ProjectModel,
)
from prm.infrastructure.db.models.resource_status import ResourceStatusModel
from prm.infrastructure.db.models.role import RoleModel
from prm.infrastructure.db.models.system import SystemConfigurationModel
from prm.infrastructure.db.models.timesheet import TimesheetEntryModel, TimesheetWeekModel
from prm.infrastructure.db.models.user import UserModel
from prm.infrastructure.db.models.user_skill import SkillModel, UserSkillModel

__all__ = [
    "AllocationModel",
    "DepartmentModel",
    "DesignationModel",
    "EmailVerificationOtpModel",
    "MilestoneModel",
    "PermissionModel",
    "ProjectHealthSnapshotModel",
    "ProjectModel",
    "ResourceStatusModel",
    "RoleModel",
    "RolePermissionModel",
    "SkillModel",
    "SystemConfigurationModel",
    "TimesheetEntryModel",
    "TimesheetWeekModel",
    "UserModel",
    "UserSkillModel",
]
