"""create initial schema

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-06-06

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "role",
            sa.Enum("ADMIN", "MANAGER", "EMPLOYEE", name="role", native_enum=False, length=20),
            nullable=False,
        ),
        sa.Column(
            "account_status",
            sa.Enum("ACTIVE", "INACTIVE", name="user_account_status", native_enum=False, length=20),
            nullable=False,
        ),
        sa.Column("force_password_change", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("username"),
    )
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=False)

    op.create_table(
        "employees",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("department", sa.String(length=255), nullable=False),
        sa.Column("designation", sa.String(length=255), nullable=False),
        sa.Column(
            "work_status",
            sa.Enum("BENCH", "ALLOCATED", name="employee_work_status", native_enum=False, length=20),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("current_utilisation_percent", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )

    op.create_table(
        "skills",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "category",
            sa.Enum(
                "BACKEND",
                "FRONTEND",
                "DEVOPS",
                "QA",
                "OTHER",
                name="skill_category",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("is_predefined", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "system_configurations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "llm_provider",
            sa.Enum("GEMINI", "GROQ", name="llm_provider", native_enum=False, length=20),
            nullable=False,
        ),
        sa.Column("llm_api_key_encrypted", sa.String(length=512), nullable=True),
        sa.Column("scheduler_interval_hours", sa.Integer(), nullable=False),
        sa.Column("max_weekly_hours", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("PLANNED", "ACTIVE", "ON_HOLD", name="project_status", native_enum=False, length=20),
            nullable=False,
        ),
        sa.Column("manager_user_id", sa.Integer(), nullable=False),
        sa.Column(
            "health_status",
            sa.Enum(
                "ON_TRACK",
                "ATTENTION",
                "AT_RISK",
                name="project_health_status",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("health_computed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["manager_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_projects_manager_user_id"), "projects", ["manager_user_id"], unique=False)

    op.create_table(
        "employee_skills",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("skill_id", sa.Integer(), nullable=False),
        sa.Column(
            "proficiency",
            sa.Enum(
                "BEGINNER",
                "INTERMEDIATE",
                "ADVANCED",
                name="proficiency_level",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("employee_id", "skill_id", name="uq_employee_skill"),
    )
    op.create_index(
        op.f("ix_employee_skills_employee_id"), "employee_skills", ["employee_id"], unique=False
    )
    op.create_index(op.f("ix_employee_skills_skill_id"), "employee_skills", ["skill_id"], unique=False)

    op.create_table(
        "milestones",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "NOT_STARTED",
                "IN_PROGRESS",
                "DONE",
                name="milestone_status",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("sequence_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_milestones_project_id"), "milestones", ["project_id"], unique=False)

    op.create_table(
        "project_health_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "ON_TRACK",
                "ATTENTION",
                "AT_RISK",
                name="project_health_status",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("risk_flags", sa.ARRAY(sa.String(length=255)), nullable=False),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_project_health_snapshots_project_id"),
        "project_health_snapshots",
        ["project_id"],
        unique=False,
    )

    op.create_table(
        "allocations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("utilisation_percent", sa.Integer(), nullable=False),
        sa.Column("from_date", sa.Date(), nullable=False),
        sa.Column("to_date", sa.Date(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("ACTIVE", "ENDED", name="allocation_status", native_enum=False, length=20),
            nullable=False,
        ),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_allocations_created_by_user_id"), "allocations", ["created_by_user_id"], unique=False
    )
    op.create_index(op.f("ix_allocations_employee_id"), "allocations", ["employee_id"], unique=False)
    op.create_index(op.f("ix_allocations_project_id"), "allocations", ["project_id"], unique=False)

    op.create_table(
        "timesheet_weeks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("week_start_date", sa.Date(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("SUBMITTED", "MISSED", name="timesheet_week_status", native_enum=False, length=20),
            nullable=False,
        ),
        sa.Column("total_hours", sa.Integer(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_timesheet_weeks_employee_id"), "timesheet_weeks", ["employee_id"], unique=False
    )

    op.create_table(
        "timesheet_entries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("timesheet_week_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("hours_worked", sa.Integer(), nullable=False),
        sa.Column(
            "activity_tags",
            sa.ARRAY(
                sa.Enum(
                    "BACKEND_API",
                    "MICROSERVICES",
                    "DATABASE_DESIGN",
                    "WEBSOCKET",
                    "FRONTEND",
                    "CODE_REVIEW",
                    "BUG_FIXING",
                    "DEVOPS",
                    "TESTING_QA",
                    "DOCUMENTATION",
                    "OTHER",
                    name="activity_tag",
                    native_enum=False,
                    length=30,
                )
            ),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["timesheet_week_id"], ["timesheet_weeks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_timesheet_entries_project_id"), "timesheet_entries", ["project_id"], unique=False
    )
    op.create_index(
        op.f("ix_timesheet_entries_timesheet_week_id"),
        "timesheet_entries",
        ["timesheet_week_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("timesheet_entries")
    op.drop_table("timesheet_weeks")
    op.drop_table("allocations")
    op.drop_table("project_health_snapshots")
    op.drop_table("milestones")
    op.drop_table("employee_skills")
    op.drop_table("projects")
    op.drop_table("system_configurations")
    op.drop_table("skills")
    op.drop_table("employees")
    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_table("users")
