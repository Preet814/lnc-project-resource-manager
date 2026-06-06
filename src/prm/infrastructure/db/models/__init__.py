"""ORM model registry — import all models so Alembic sees metadata."""

from prm.infrastructure.db.models.allocation import AllocationModel
from prm.infrastructure.db.models.employee import EmployeeModel, EmployeeSkillModel, SkillModel
from prm.infrastructure.db.models.project import (
    MilestoneModel,
    ProjectHealthSnapshotModel,
    ProjectModel,
)
from prm.infrastructure.db.models.system import SystemConfigurationModel
from prm.infrastructure.db.models.timesheet import TimesheetEntryModel, TimesheetWeekModel
from prm.infrastructure.db.models.user import UserModel

__all__ = [
    "AllocationModel",
    "EmployeeModel",
    "EmployeeSkillModel",
    "MilestoneModel",
    "ProjectHealthSnapshotModel",
    "ProjectModel",
    "SkillModel",
    "SystemConfigurationModel",
    "TimesheetEntryModel",
    "TimesheetWeekModel",
    "UserModel",
]
