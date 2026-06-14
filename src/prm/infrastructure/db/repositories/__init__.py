"""SQLAlchemy repository implementations."""

from prm.infrastructure.db.repositories.allocation_repository import (
    SqlAlchemyAllocationRepository,
)
from prm.infrastructure.db.repositories.email_verification_otp_repository import (
    SqlAlchemyEmailVerificationOtpRepository,
)
from prm.infrastructure.db.repositories.lookup_repository import SqlAlchemyLookupRepository
from prm.infrastructure.db.repositories.milestone_repository import SqlAlchemyMilestoneRepository
from prm.infrastructure.db.repositories.permission_repository import (
    SqlAlchemyPermissionRepository,
)
from prm.infrastructure.db.repositories.project_health_snapshot_repository import (
    SqlAlchemyProjectHealthSnapshotRepository,
)
from prm.infrastructure.db.repositories.project_repository import SqlAlchemyProjectRepository
from prm.infrastructure.db.repositories.skill_repository import SqlAlchemySkillRepository
from prm.infrastructure.db.repositories.system_configuration_repository import (
    SqlAlchemySystemConfigurationRepository,
)
from prm.infrastructure.db.repositories.timesheet_repository import SqlAlchemyTimesheetRepository
from prm.infrastructure.db.repositories.user_repository import SqlAlchemyUserRepository
from prm.infrastructure.db.repositories.user_skill_repository import SqlAlchemyUserSkillRepository

__all__ = [
    "SqlAlchemyAllocationRepository",
    "SqlAlchemyEmailVerificationOtpRepository",
    "SqlAlchemyLookupRepository",
    "SqlAlchemyMilestoneRepository",
    "SqlAlchemyPermissionRepository",
    "SqlAlchemyProjectHealthSnapshotRepository",
    "SqlAlchemyProjectRepository",
    "SqlAlchemySkillRepository",
    "SqlAlchemySystemConfigurationRepository",
    "SqlAlchemyTimesheetRepository",
    "SqlAlchemyUserRepository",
    "SqlAlchemyUserSkillRepository",
]
