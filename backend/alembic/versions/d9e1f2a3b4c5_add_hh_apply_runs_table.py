"""add hh apply runs table

Revision ID: d9e1f2a3b4c5
Revises: c4d5e6f7a8b9
Create Date: 2026-04-05 02:20:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "d9e1f2a3b4c5"
down_revision: Union[str, Sequence[str], None] = "c4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "hh_apply_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("vacancy_id", sa.Integer(), nullable=False),
        sa.Column("hh_resume_managed_id", sa.Integer(), nullable=False),
        sa.Column("source_cover_letter_version_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("hh_vacancy_url", sa.String(length=1024), nullable=True),
        sa.Column("result_type", sa.String(length=64), nullable=True),
        sa.Column("result_message", sa.String(length=160), nullable=True),
        sa.Column("hh_response_ref", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["hh_resume_managed_id"], ["hh_managed_resumes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_cover_letter_version_id"], ["cover_letter_versions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["vacancy_id"], ["vacancies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_hh_apply_runs_id"), "hh_apply_runs", ["id"], unique=False)
    op.create_index(op.f("ix_hh_apply_runs_user_id"), "hh_apply_runs", ["user_id"], unique=False)
    op.create_index(op.f("ix_hh_apply_runs_profile_id"), "hh_apply_runs", ["profile_id"], unique=False)
    op.create_index(op.f("ix_hh_apply_runs_vacancy_id"), "hh_apply_runs", ["vacancy_id"], unique=False)
    op.create_index(op.f("ix_hh_apply_runs_hh_resume_managed_id"), "hh_apply_runs", ["hh_resume_managed_id"], unique=False)
    op.create_index(op.f("ix_hh_apply_runs_source_cover_letter_version_id"), "hh_apply_runs", ["source_cover_letter_version_id"], unique=False)
    op.create_index(op.f("ix_hh_apply_runs_status"), "hh_apply_runs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_hh_apply_runs_status"), table_name="hh_apply_runs")
    op.drop_index(op.f("ix_hh_apply_runs_source_cover_letter_version_id"), table_name="hh_apply_runs")
    op.drop_index(op.f("ix_hh_apply_runs_hh_resume_managed_id"), table_name="hh_apply_runs")
    op.drop_index(op.f("ix_hh_apply_runs_vacancy_id"), table_name="hh_apply_runs")
    op.drop_index(op.f("ix_hh_apply_runs_profile_id"), table_name="hh_apply_runs")
    op.drop_index(op.f("ix_hh_apply_runs_user_id"), table_name="hh_apply_runs")
    op.drop_index(op.f("ix_hh_apply_runs_id"), table_name="hh_apply_runs")
    op.drop_table("hh_apply_runs")
