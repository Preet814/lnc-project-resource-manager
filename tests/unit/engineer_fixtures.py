"""Shared helpers for unit tests using the unified user/engineer model."""

from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import JSON, create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from prm.api.app import create_app
from prm.domain.enums import ResourceWorkStatus, Role, UserAccountStatus
from prm.infrastructure.db.models import (
    AllocationModel,
    DepartmentModel,
    DesignationModel,
    MilestoneModel,
    PermissionModel,
    ProjectHealthSnapshotModel,
    ProjectModel,
    ResourceStatusModel,
    RoleModel,
    RolePermissionModel,
    SkillModel,
    SystemConfigurationModel,
    TimesheetEntryModel,
    TimesheetSubmissionRestoreModel,
    TimesheetWeekModel,
    UserModel,
    UserSkillModel,
)
from prm.infrastructure.db.rbac_seed import (
    default_department_id,
    default_designation_id,
    role_id_for_code,
    seed_rbac_lookups,
)
from prm.infrastructure.db.repositories import SqlAlchemyUserRepository
from prm.infrastructure.db.session import get_db_session
from prm.infrastructure.security.password import BcryptPasswordHasher


def create_sqlite_engine() -> Engine:
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def create_rbac_tables(bind) -> None:
    RoleModel.__table__.create(bind, checkfirst=True)
    DepartmentModel.__table__.create(bind, checkfirst=True)
    DesignationModel.__table__.create(bind, checkfirst=True)
    PermissionModel.__table__.create(bind, checkfirst=True)
    RolePermissionModel.__table__.create(bind, checkfirst=True)
    UserModel.__table__.create(bind, checkfirst=True)
    ResourceStatusModel.__table__.create(bind, checkfirst=True)


def create_memory_session(*, include_project: bool = False) -> Session:
    engine = create_engine("sqlite:///:memory:")
    create_rbac_tables(engine)
    if include_project:
        ProjectModel.__table__.create(engine, checkfirst=True)
        MilestoneModel.__table__.create(engine, checkfirst=True)
        ProjectHealthSnapshotModel.__table__.c.risk_flags.type = JSON()
        ProjectHealthSnapshotModel.__table__.create(engine, checkfirst=True)
    return Session(engine)


def seed_rbac(session: Session) -> None:
    seed_rbac_lookups(session)
    session.flush()


def create_user(
    session: Session,
    *,
    username: str,
    email: str,
    full_name: str,
    role: Role,
    manager_id: int | None = None,
    department_name: str = "Backend",
    designation_name: str = "SE",
) -> int:
    seed_rbac(session)
    repo = SqlAlchemyUserRepository(session)
    hasher = BcryptPasswordHasher()
    created = repo.create(
        full_name=full_name,
        username=username,
        email=email,
        password_hash=hasher.hash("TempPass1"),
        role_id=role_id_for_code(session, role.value),
        department_id=default_department_id(session, name=department_name),
        designation_id=default_designation_id(session, name=designation_name),
        manager_id=manager_id,
        account_status=UserAccountStatus.ACTIVE,
    )
    session.flush()
    return created.id


def set_engineer_status(
    session: Session,
    user_id: int,
    *,
    utilisation_percent: int,
    work_status: ResourceWorkStatus,
) -> None:
    SqlAlchemyUserRepository(session).update_resource_status(
        user_id,
        utilisation_percent=utilisation_percent,
        work_status=work_status,
    )
    session.flush()


def mark_user_onboarded(
    session: Session,
    *,
    username: str,
    password: str | None = None,
) -> None:
    """Clear onboarding gates so route tests can call protected endpoints."""
    model = session.scalar(select(UserModel).where(UserModel.username == username))
    if model is None:
        raise AssertionError(f"User {username!r} not found.")
    if password is not None:
        model.password_hash = BcryptPasswordHasher().hash(password)
    model.force_password_change = False
    model.email_verified = True
    session.flush()


def create_allocation_tables(session: Session) -> None:
    AllocationModel.__table__.create(session.get_bind(), checkfirst=True)


def create_timesheet_tables(session: Session) -> None:
    TimesheetWeekModel.__table__.create(session.get_bind(), checkfirst=True)
    TimesheetEntryModel.__table__.c.activity_tags.type = JSON()
    TimesheetEntryModel.__table__.create(session.get_bind(), checkfirst=True)
    TimesheetSubmissionRestoreModel.__table__.create(session.get_bind(), checkfirst=True)


def create_skill_tables(session: Session) -> None:
    SkillModel.__table__.create(session.get_bind(), checkfirst=True)
    UserSkillModel.__table__.create(session.get_bind(), checkfirst=True)


def create_config_table(session: Session) -> None:
    SystemConfigurationModel.__table__.create(session.get_bind(), checkfirst=True)


def create_route_tables(
    engine: Engine,
    *,
    include_project: bool = False,
    include_allocation: bool = False,
    include_timesheet: bool = False,
    include_skill: bool = False,
    include_config: bool = False,
) -> None:
    create_rbac_tables(engine)
    if include_project:
        ProjectModel.__table__.create(engine, checkfirst=True)
        MilestoneModel.__table__.create(engine, checkfirst=True)
        ProjectHealthSnapshotModel.__table__.c.risk_flags.type = JSON()
        ProjectHealthSnapshotModel.__table__.create(engine, checkfirst=True)
    if include_allocation:
        AllocationModel.__table__.create(engine, checkfirst=True)
    if include_timesheet:
        TimesheetWeekModel.__table__.create(engine, checkfirst=True)
        TimesheetEntryModel.__table__.c.activity_tags.type = JSON()
        TimesheetEntryModel.__table__.create(engine, checkfirst=True)
        TimesheetSubmissionRestoreModel.__table__.create(engine, checkfirst=True)
    if include_skill:
        SkillModel.__table__.create(engine, checkfirst=True)
        UserSkillModel.__table__.create(engine, checkfirst=True)
    if include_config:
        SystemConfigurationModel.__table__.create(engine, checkfirst=True)


def build_test_client(engine: Engine) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        db = Session(engine)
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db_session] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
