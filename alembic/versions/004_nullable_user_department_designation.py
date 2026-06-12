"""Allow nullable department and designation on users.

Revision ID: 004_nullable_dept_desig
Revises: 003_target_erd
Create Date: 2026-06-11

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "004_nullable_dept_desig"
down_revision: str | None = "003_target_erd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("users", "department_id", existing_type=sa.Integer(), nullable=True)
    op.alter_column("users", "designation_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    op.execute(
        """
        UPDATE users SET department_id = (
            SELECT id FROM departments WHERE name = 'IT' LIMIT 1
        ) WHERE department_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE users SET designation_id = (
            SELECT id FROM designations WHERE name = 'SE' LIMIT 1
        ) WHERE designation_id IS NULL
        """
    )
    op.alter_column("users", "department_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column("users", "designation_id", existing_type=sa.Integer(), nullable=False)
