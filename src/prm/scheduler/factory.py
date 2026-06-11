"""Construct SchedulerService with SQLAlchemy repositories."""

from sqlalchemy.orm import Session

from prm.application.health_rule_engine import HealthRuleEngine
from prm.application.scheduler_service import SchedulerService
from prm.application.utilisation_calculator import UtilisationCalculator
from prm.infrastructure.db.repositories import (
    SqlAlchemyAllocationRepository,
    SqlAlchemyMilestoneRepository,
    SqlAlchemyProjectHealthSnapshotRepository,
    SqlAlchemyProjectRepository,
    SqlAlchemySystemConfigurationRepository,
    SqlAlchemyTimesheetRepository,
    SqlAlchemyUserRepository,
)


def create_scheduler_service(session: Session) -> SchedulerService:
    """Build a scheduler service bound to one database session."""
    allocation_repository = SqlAlchemyAllocationRepository(session)
    return SchedulerService(
        user_repository=SqlAlchemyUserRepository(session),
        allocation_repository=allocation_repository,
        project_repository=SqlAlchemyProjectRepository(session),
        milestone_repository=SqlAlchemyMilestoneRepository(session),
        timesheet_repository=SqlAlchemyTimesheetRepository(session),
        health_snapshot_repository=SqlAlchemyProjectHealthSnapshotRepository(session),
        config_repository=SqlAlchemySystemConfigurationRepository(session),
        utilisation=UtilisationCalculator(allocation_repository),
        health_engine=HealthRuleEngine(),
    )
