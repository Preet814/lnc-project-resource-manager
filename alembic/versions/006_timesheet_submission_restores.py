"""Add manager timesheet submission restore records.

Revision ID: 006_timesheet_restores
Revises: 005_email_verification
Create Date: 2026-06-20

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "006_timesheet_restores"
down_revision: str | None = "005_email_verification"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "timesheet_submission_restores",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("week_start_date", sa.Date(), nullable=False),
        sa.Column("restored_by_user_id", sa.Integer(), nullable=False),
        sa.Column(
            "restored_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["restored_by_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "week_start_date",
            name="uq_timesheet_submission_restores_user_week",
        ),
    )
    op.create_index(
        "ix_timesheet_submission_restores_user_id",
        "timesheet_submission_restores",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_timesheet_submission_restores_user_id",
        table_name="timesheet_submission_restores",
    )
    op.drop_table("timesheet_submission_restores")
