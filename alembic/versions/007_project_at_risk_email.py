"""Add last_at_risk_email_sent_at to projects for notification cooldown.

Revision ID: 007_project_at_risk_email
Revises: 006_timesheet_restores
Create Date: 2026-06-20

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "007_project_at_risk_email"
down_revision: str | None = "006_timesheet_restores"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("last_at_risk_email_sent_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("projects", "last_at_risk_email_sent_at")
