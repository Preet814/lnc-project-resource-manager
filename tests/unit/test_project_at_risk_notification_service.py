"""Unit tests for ProjectAtRiskNotificationService."""

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import JSON
from sqlalchemy.orm import Session

from prm.application.project_at_risk_notification_service import (
    ProjectAtRiskNotificationService,
)
from prm.domain.constants import (
    HEALTH_RESOURCES_ALLOCATED_FLAG,
    PROJECT_AT_RISK_EMAIL_SUBJECT,
)
from prm.domain.enums import (
    MilestoneStatus,
    ProficiencyLevel,
    ProjectHealthStatus,
    ProjectStatus,
    ResourceWorkStatus,
    Role,
    SkillCategory,
)
from prm.infrastructure.db.models import MilestoneModel, ProjectHealthSnapshotModel
from prm.infrastructure.db.repositories import (
    SqlAlchemyMilestoneRepository,
    SqlAlchemyProjectHealthSnapshotRepository,
    SqlAlchemyProjectRepository,
    SqlAlchemySkillRepository,
    SqlAlchemyUserRepository,
    SqlAlchemyUserSkillRepository,
)
from tests.unit.engineer_fixtures import (
    create_memory_session,
    create_skill_tables,
    create_user,
    seed_rbac,
    set_engineer_status,
)
from tests.unit.test_email_verification_service import FakeEmailSender

AS_OF = datetime(2026, 5, 20, 10, 0, tzinfo=UTC)


def _session() -> Session:
    session = create_memory_session(include_project=True)
    create_skill_tables(session)
    ProjectHealthSnapshotModel.__table__.c.risk_flags.type = JSON()
    ProjectHealthSnapshotModel.__table__.create(session.get_bind(), checkfirst=True)
    return session


def _service(
    session: Session,
    email_sender: FakeEmailSender,
    *,
    notifications_enabled: bool = True,
    reminder_days: int = 7,
) -> ProjectAtRiskNotificationService:
    return ProjectAtRiskNotificationService(
        project_repository=SqlAlchemyProjectRepository(session),
        user_repository=SqlAlchemyUserRepository(session),
        milestone_repository=SqlAlchemyMilestoneRepository(session),
        health_snapshot_repository=SqlAlchemyProjectHealthSnapshotRepository(session),
        user_skill_repository=SqlAlchemyUserSkillRepository(session),
        skill_repository=SqlAlchemySkillRepository(session),
        email_sender=email_sender,
        notifications_enabled=notifications_enabled,
        reminder_days=reminder_days,
    )


def _seed_project_context(
    session: Session,
    *,
    manager_email_verified: bool = True,
    include_bench_engineer: bool = True,
) -> tuple[int, int]:
    seed_rbac(session)
    user_repo = SqlAlchemyUserRepository(session)
    manager_id = create_user(
        session,
        username="manager",
        email="manager@example.test",
        full_name="Manager User",
        role=Role.MANAGER,
    )
    if manager_email_verified:
        user_repo.update_email_verified(manager_id, email_verified=True)

    if include_bench_engineer:
        bench_id = create_user(
            session,
            username="bench",
            email="bench@example.test",
            full_name="Priya Sharma",
            role=Role.ENGINEER,
            manager_id=manager_id,
        )
        set_engineer_status(
            session,
            bench_id,
            utilisation_percent=0,
            work_status=ResourceWorkStatus.BENCH,
        )
        skill_repo = SqlAlchemySkillRepository(session)
        python_skill = skill_repo.create(name="Python", category=SkillCategory.BACKEND)
        SqlAlchemyUserSkillRepository(session).assign(
            user_id=bench_id,
            skill_id=python_skill.id,
            proficiency=ProficiencyLevel.INTERMEDIATE,
        )

    project = SqlAlchemyProjectRepository(session).create(
        name="Alpha Portal",
        description="Customer portal rewrite",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 6, 30),
        status=ProjectStatus.ACTIVE,
        manager_user_id=manager_id,
    )
    session.add(
        MilestoneModel(
            project_id=project.id,
            title="Backend API",
            due_date=date(2026, 5, 15),
            status=MilestoneStatus.IN_PROGRESS,
            sequence_order=1,
        )
    )
    SqlAlchemyProjectHealthSnapshotRepository(session).save(
        project_id=project.id,
        status=ProjectHealthStatus.AT_RISK,
        risk_flags=(
            "Backend API milestone is 5 days overdue",
            HEALTH_RESOURCES_ALLOCATED_FLAG,
        ),
        computed_at=AS_OF,
    )
    session.flush()
    return manager_id, project.id


def test_sends_on_transition_to_at_risk() -> None:
    with _session() as session:
        _, project_id = _seed_project_context(session)
        session.commit()
        sender = FakeEmailSender()
        service = _service(session, sender)
        project = SqlAlchemyProjectRepository(session).find_by_id(project_id)
        assert project is not None

        sent = service.maybe_notify_at_risk(
            project,
            previous_status=ProjectHealthStatus.ON_TRACK,
            new_status=ProjectHealthStatus.AT_RISK,
            as_of=AS_OF,
        )

        updated = SqlAlchemyProjectRepository(session).find_by_id(project_id)
        assert sent is True
        assert len(sender.messages) == 1
        assert sender.messages[0][0] == "manager@example.test"
        assert sender.messages[0][1] == PROJECT_AT_RISK_EMAIL_SUBJECT.format(
            name="Alpha Portal"
        )
        assert updated is not None
        assert updated.last_at_risk_email_sent_at == AS_OF


def test_skips_when_still_at_risk_within_7_days() -> None:
    with _session() as session:
        _, project_id = _seed_project_context(session)
        project_repo = SqlAlchemyProjectRepository(session)
        last_sent = AS_OF - timedelta(days=3)
        project_repo.update_last_at_risk_email_sent(project_id, last_sent)
        session.commit()
        sender = FakeEmailSender()
        service = _service(session, sender)
        project = project_repo.find_by_id(project_id)
        assert project is not None

        sent = service.maybe_notify_at_risk(
            project,
            previous_status=ProjectHealthStatus.AT_RISK,
            new_status=ProjectHealthStatus.AT_RISK,
            as_of=AS_OF,
        )

        assert sent is False
        assert sender.messages == []
        unchanged = project_repo.find_by_id(project_id)
        assert unchanged is not None
        assert unchanged.last_at_risk_email_sent_at == last_sent


def test_sends_weekly_reminder_after_7_days() -> None:
    with _session() as session:
        _, project_id = _seed_project_context(session)
        project_repo = SqlAlchemyProjectRepository(session)
        last_sent = AS_OF - timedelta(days=8)
        project_repo.update_last_at_risk_email_sent(project_id, last_sent)
        session.commit()
        sender = FakeEmailSender()
        service = _service(session, sender)
        project = project_repo.find_by_id(project_id)
        assert project is not None

        sent = service.maybe_notify_at_risk(
            project,
            previous_status=ProjectHealthStatus.AT_RISK,
            new_status=ProjectHealthStatus.AT_RISK,
            as_of=AS_OF,
        )

        updated = project_repo.find_by_id(project_id)
        assert sent is True
        assert len(sender.messages) == 1
        assert updated is not None
        assert updated.last_at_risk_email_sent_at == AS_OF


def test_clears_last_sent_when_recovered() -> None:
    with _session() as session:
        _, project_id = _seed_project_context(session)
        project_repo = SqlAlchemyProjectRepository(session)
        project_repo.update_last_at_risk_email_sent(project_id, AS_OF)
        session.commit()
        sender = FakeEmailSender()
        service = _service(session, sender)
        project = project_repo.find_by_id(project_id)
        assert project is not None

        sent = service.maybe_notify_at_risk(
            project,
            previous_status=ProjectHealthStatus.AT_RISK,
            new_status=ProjectHealthStatus.ON_TRACK,
            as_of=AS_OF + timedelta(days=1),
        )

        updated = project_repo.find_by_id(project_id)
        assert sent is False
        assert sender.messages == []
        assert updated is not None
        assert updated.last_at_risk_email_sent_at is None


def test_resends_after_recovery_and_re_at_risk() -> None:
    with _session() as session:
        _, project_id = _seed_project_context(session)
        project_repo = SqlAlchemyProjectRepository(session)
        project_repo.update_last_at_risk_email_sent(project_id, AS_OF)
        session.commit()
        sender = FakeEmailSender()
        service = _service(session, sender)
        project = project_repo.find_by_id(project_id)
        assert project is not None

        service.maybe_notify_at_risk(
            project,
            previous_status=ProjectHealthStatus.AT_RISK,
            new_status=ProjectHealthStatus.ON_TRACK,
            as_of=AS_OF + timedelta(days=1),
        )
        recovered = project_repo.find_by_id(project_id)
        assert recovered is not None
        assert recovered.last_at_risk_email_sent_at is None

        sent = service.maybe_notify_at_risk(
            recovered,
            previous_status=ProjectHealthStatus.ATTENTION,
            new_status=ProjectHealthStatus.AT_RISK,
            as_of=AS_OF + timedelta(days=2),
        )

        assert sent is True
        assert len(sender.messages) == 1


def test_skips_unverified_manager() -> None:
    with _session() as session:
        _, project_id = _seed_project_context(session, manager_email_verified=False)
        session.commit()
        sender = FakeEmailSender()
        service = _service(session, sender)
        project = SqlAlchemyProjectRepository(session).find_by_id(project_id)
        assert project is not None

        sent = service.maybe_notify_at_risk(
            project,
            previous_status=ProjectHealthStatus.ON_TRACK,
            new_status=ProjectHealthStatus.AT_RISK,
            as_of=AS_OF,
        )

        updated = SqlAlchemyProjectRepository(session).find_by_id(project_id)
        assert sent is False
        assert sender.messages == []
        assert updated is not None
        assert updated.last_at_risk_email_sent_at is None


def test_email_includes_milestones_and_bench() -> None:
    with _session() as session:
        _, project_id = _seed_project_context(session)
        session.commit()
        sender = FakeEmailSender()
        service = _service(session, sender)
        project = SqlAlchemyProjectRepository(session).find_by_id(project_id)
        assert project is not None

        service.maybe_notify_at_risk(
            project,
            previous_status=ProjectHealthStatus.ON_TRACK,
            new_status=ProjectHealthStatus.AT_RISK,
            as_of=AS_OF,
        )

        body = sender.messages[0][2]
        assert "Backend API" in body
        assert "2026-05-15" in body
        assert "Backend API milestone is 5 days overdue" in body
        assert HEALTH_RESOURCES_ALLOCATED_FLAG not in body
        assert "Priya Sharma" in body
        assert "Python" in body
        assert "Red (AT RISK)" in body
