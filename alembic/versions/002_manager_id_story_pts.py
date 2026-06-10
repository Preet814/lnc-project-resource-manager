"""add manager_id to employees and story points to projects/milestones

Revision ID: 002_manager_id_story_pts
Revises: 001_initial_schema
Create Date: 2026-06-09

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "002_manager_id_story_pts"
down_revision: str | None = "001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "employees",
        sa.Column("manager_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_employees_manager_id_users",
        "employees",
        "users",
        ["manager_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_employees_manager_id"),
        "employees",
        ["manager_id"],
        unique=False,
    )

    op.add_column(
        "projects",
        sa.Column(
            "total_story_points",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.alter_column("projects", "total_story_points", server_default=None)

    op.add_column(
        "milestones",
        sa.Column(
            "story_points",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.alter_column("milestones", "story_points", server_default=None)


def downgrade() -> None:
    op.drop_column("milestones", "story_points")
    op.drop_column("projects", "total_story_points")
    op.drop_index(op.f("ix_employees_manager_id"), table_name="employees")
    op.drop_constraint("fk_employees_manager_id_users", "employees", type_="foreignkey")
    op.drop_column("employees", "manager_id")
