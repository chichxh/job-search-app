"""add hh managed resumes table

Revision ID: b1c2d3e4f5a7
Revises: aa1b2c3d4e6f
Create Date: 2026-04-05 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b1c2d3e4f5a7"
down_revision: Union[str, Sequence[str], None] = "aa1b2c3d4e6f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "hh_managed_resumes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("source_resume_version_id", sa.Integer(), nullable=True),
        sa.Column("vacancy_id", sa.Integer(), nullable=True),
        sa.Column("hh_resume_external_id", sa.String(length=128), nullable=True),
        sa.Column("hh_resume_url", sa.String(length=1024), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft_local"),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=64), nullable=True),
        sa.Column("last_error_message", sa.String(length=160), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_resume_version_id"], ["resume_versions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["vacancy_id"], ["vacancies.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_hh_managed_resumes_id", "hh_managed_resumes", ["id"], unique=False)
    op.create_index("ix_hh_managed_resumes_user_id", "hh_managed_resumes", ["user_id"], unique=False)
    op.create_index("ix_hh_managed_resumes_profile_id", "hh_managed_resumes", ["profile_id"], unique=False)
    op.create_index(
        "ix_hh_managed_resumes_source_resume_version_id",
        "hh_managed_resumes",
        ["source_resume_version_id"],
        unique=False,
    )
    op.create_index("ix_hh_managed_resumes_vacancy_id", "hh_managed_resumes", ["vacancy_id"], unique=False)
    op.create_index(
        "ix_hh_managed_resumes_hh_resume_external_id",
        "hh_managed_resumes",
        ["hh_resume_external_id"],
        unique=False,
    )
    op.create_index("ix_hh_managed_resumes_status", "hh_managed_resumes", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_hh_managed_resumes_status", table_name="hh_managed_resumes")
    op.drop_index("ix_hh_managed_resumes_hh_resume_external_id", table_name="hh_managed_resumes")
    op.drop_index("ix_hh_managed_resumes_vacancy_id", table_name="hh_managed_resumes")
    op.drop_index("ix_hh_managed_resumes_source_resume_version_id", table_name="hh_managed_resumes")
    op.drop_index("ix_hh_managed_resumes_profile_id", table_name="hh_managed_resumes")
    op.drop_index("ix_hh_managed_resumes_user_id", table_name="hh_managed_resumes")
    op.drop_index("ix_hh_managed_resumes_id", table_name="hh_managed_resumes")
    op.drop_table("hh_managed_resumes")
