"""Construct scheduler services with SQLAlchemy repositories."""

from sqlalchemy.orm import Session

from prm.api.settings import Settings, get_settings
from prm.application.health_rule_engine import HealthRuleEngine
from prm.application.project_at_risk_notification_service import (
    ProjectAtRiskNotificationService,
)
from prm.application.scheduler_service import SchedulerService
from prm.application.timesheet_notification_service import TimesheetNotificationService
from prm.application.utilisation_calculator import UtilisationCalculator
from prm.infrastructure.db.repositories import (
    SqlAlchemyAllocationRepository,
    SqlAlchemyMilestoneRepository,
    SqlAlchemyProjectHealthSnapshotRepository,
    SqlAlchemyProjectRepository,
    SqlAlchemySkillRepository,
    SqlAlchemySystemConfigurationRepository,
    SqlAlchemyTimesheetRepository,
    SqlAlchemyUserRepository,
    SqlAlchemyUserSkillRepository,
)
from prm.infrastructure.email.factory import create_email_sender


def create_project_at_risk_notification_service(
    session: Session,
    settings: Settings,
) -> ProjectAtRiskNotificationService:
    """Build a project at-risk notification service bound to one database session."""
    return ProjectAtRiskNotificationService(
        project_repository=SqlAlchemyProjectRepository(session),
        user_repository=SqlAlchemyUserRepository(session),
        milestone_repository=SqlAlchemyMilestoneRepository(session),
        health_snapshot_repository=SqlAlchemyProjectHealthSnapshotRepository(session),
        user_skill_repository=SqlAlchemyUserSkillRepository(session),
        skill_repository=SqlAlchemySkillRepository(session),
        email_sender=create_email_sender(settings),
        notifications_enabled=settings.project_at_risk_notifications_enabled,
        reminder_days=settings.project_at_risk_reminder_days,
    )


def create_scheduler_service(
    session: Session,
    settings: Settings | None = None,
) -> SchedulerService:
    """Build a scheduler service bound to one database session."""
    resolved = settings or get_settings()
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
        at_risk_notifier=create_project_at_risk_notification_service(session, resolved),
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
