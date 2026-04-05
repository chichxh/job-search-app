"""add hh resume visibility fields

Revision ID: c4d5e6f7a8b9
Revises: b1c2d3e4f5a7
Create Date: 2026-04-05 00:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, Sequence[str], None] = "b1c2d3e4f5a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "hh_managed_resumes",
        sa.Column("desired_visibility_mode", sa.String(length=32), nullable=False, server_default="hidden_from_all"),
    )
    op.add_column(
        "hh_managed_resumes",
        sa.Column("current_visibility_mode", sa.String(length=32), nullable=False, server_default="unknown"),
    )
    op.add_column("hh_managed_resumes", sa.Column("visibility_last_checked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("hh_managed_resumes", sa.Column("visibility_last_changed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("hh_managed_resumes", sa.Column("visibility_status", sa.String(length=32), nullable=False, server_default="idle"))
    op.add_column("hh_managed_resumes", sa.Column("visibility_error_code", sa.String(length=64), nullable=True))
    op.add_column("hh_managed_resumes", sa.Column("visibility_error_message", sa.String(length=160), nullable=True))
    op.create_index("ix_hh_managed_resumes_desired_visibility_mode", "hh_managed_resumes", ["desired_visibility_mode"], unique=False)
    op.create_index("ix_hh_managed_resumes_current_visibility_mode", "hh_managed_resumes", ["current_visibility_mode"], unique=False)
    op.create_index("ix_hh_managed_resumes_visibility_status", "hh_managed_resumes", ["visibility_status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_hh_managed_resumes_visibility_status", table_name="hh_managed_resumes")
    op.drop_index("ix_hh_managed_resumes_current_visibility_mode", table_name="hh_managed_resumes")
    op.drop_index("ix_hh_managed_resumes_desired_visibility_mode", table_name="hh_managed_resumes")
    op.drop_column("hh_managed_resumes", "visibility_error_message")
    op.drop_column("hh_managed_resumes", "visibility_error_code")
    op.drop_column("hh_managed_resumes", "visibility_status")
    op.drop_column("hh_managed_resumes", "visibility_last_changed_at")
    op.drop_column("hh_managed_resumes", "visibility_last_checked_at")
    op.drop_column("hh_managed_resumes", "current_visibility_mode")
    op.drop_column("hh_managed_resumes", "desired_visibility_mode")
