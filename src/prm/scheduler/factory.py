"""Construct scheduler services with SQLAlchemy repositories."""

from sqlalchemy.orm import Session

from prm.api.settings import Settings
from prm.application.health_rule_engine import HealthRuleEngine
from prm.application.scheduler_service import SchedulerService
from prm.application.timesheet_notification_service import TimesheetNotificationService
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
from prm.infrastructure.email.factory import create_email_sender


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


def create_timesheet_notification_service(
    session: Session,
    settings: Settings,
) -> TimesheetNotificationService:
    """Build a timesheet notification service bound to one database session."""
    return TimesheetNotificationService(
        user_repository=SqlAlchemyUserRepository(session),
        allocation_repository=SqlAlchemyAllocationRepository(session),
        timesheet_repository=SqlAlchemyTimesheetRepository(session),
        email_sender=create_email_sender(settings),
        notifications_enabled=settings.timesheet_notifications_enabled,
    )
