"""Add email verification fields and OTP storage.

Revision ID: 005_email_verification
Revises: 004_nullable_dept_desig
Create Date: 2026-06-11

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "005_email_verification"
down_revision: str | None = "004_nullable_dept_desig"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "email_verified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.alter_column("users", "email_verified", server_default=None)

    op.create_table(
        "email_verification_otps",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("otp_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "last_sent_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_email_verification_otps_user_id"),
    )
    op.create_index(
        "ix_email_verification_otps_user_id",
        "email_verification_otps",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_email_verification_otps_user_id", table_name="email_verification_otps")
    op.drop_table("email_verification_otps")
    op.drop_column("users", "email_verified")
