"""add hh automation action runs

Revision ID: f6a1b2c3d4e5
Revises: e1f3a9b7c2d4, e5f6a7b8c9d0
Create Date: 2026-04-05 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f6a1b2c3d4e5"
down_revision: Union[str, Sequence[str], None] = ("e1f3a9b7c2d4", "e5f6a7b8c9d0")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "hh_automation_action_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("action_type", sa.String(length=64), nullable=False),
        sa.Column("triggered_by", sa.String(length=32), nullable=False, server_default="user"),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=True),
        sa.Column("target_ref", sa.String(length=160), nullable=True),
        sa.Column("request_fingerprint", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="running"),
        sa.Column("operation_code", sa.String(length=64), nullable=True),
        sa.Column("safe_summary", sa.String(length=200), nullable=True),
        sa.Column("retry_of_action_id", sa.Integer(), nullable=True),
        sa.Column("parent_action_id", sa.Integer(), nullable=True),
        sa.Column("context_ref", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["parent_action_id"], ["hh_automation_action_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["retry_of_action_id"], ["hh_automation_action_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_hh_automation_action_runs_id"), "hh_automation_action_runs", ["id"], unique=False)
    op.create_index(op.f("ix_hh_automation_action_runs_user_id"), "hh_automation_action_runs", ["user_id"], unique=False)
    op.create_index(op.f("ix_hh_automation_action_runs_action_type"), "hh_automation_action_runs", ["action_type"], unique=False)
    op.create_index(op.f("ix_hh_automation_action_runs_target_type"), "hh_automation_action_runs", ["target_type"], unique=False)
    op.create_index(op.f("ix_hh_automation_action_runs_target_id"), "hh_automation_action_runs", ["target_id"], unique=False)
    op.create_index(op.f("ix_hh_automation_action_runs_request_fingerprint"), "hh_automation_action_runs", ["request_fingerprint"], unique=False)
    op.create_index(op.f("ix_hh_automation_action_runs_retry_of_action_id"), "hh_automation_action_runs", ["retry_of_action_id"], unique=False)
    op.create_index(op.f("ix_hh_automation_action_runs_parent_action_id"), "hh_automation_action_runs", ["parent_action_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_hh_automation_action_runs_parent_action_id"), table_name="hh_automation_action_runs")
    op.drop_index(op.f("ix_hh_automation_action_runs_retry_of_action_id"), table_name="hh_automation_action_runs")
    op.drop_index(op.f("ix_hh_automation_action_runs_request_fingerprint"), table_name="hh_automation_action_runs")
    op.drop_index(op.f("ix_hh_automation_action_runs_target_id"), table_name="hh_automation_action_runs")
    op.drop_index(op.f("ix_hh_automation_action_runs_target_type"), table_name="hh_automation_action_runs")
    op.drop_index(op.f("ix_hh_automation_action_runs_action_type"), table_name="hh_automation_action_runs")
    op.drop_index(op.f("ix_hh_automation_action_runs_user_id"), table_name="hh_automation_action_runs")
    op.drop_index(op.f("ix_hh_automation_action_runs_id"), table_name="hh_automation_action_runs")
    op.drop_table("hh_automation_action_runs")
