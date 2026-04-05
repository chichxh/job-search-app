"""sync hh apply runs into applications

Revision ID: e5f6a7b8c9d0
Revises: d9e1f2a3b4c5
Create Date: 2026-04-05 09:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d9e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("applications", sa.Column("last_hh_apply_run_id", sa.Integer(), nullable=True))
    op.add_column("applications", sa.Column("hh_managed_resume_id", sa.Integer(), nullable=True))
    op.add_column("applications", sa.Column("external_apply_status", sa.String(length=32), nullable=True))
    op.add_column("applications", sa.Column("last_external_apply_at", sa.DateTime(timezone=True), nullable=True))

    op.create_index(op.f("ix_applications_last_hh_apply_run_id"), "applications", ["last_hh_apply_run_id"], unique=False)
    op.create_index(op.f("ix_applications_hh_managed_resume_id"), "applications", ["hh_managed_resume_id"], unique=False)

    op.create_foreign_key(
        "fk_applications_last_hh_apply_run_id_hh_apply_runs",
        "applications",
        "hh_apply_runs",
        ["last_hh_apply_run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_applications_hh_managed_resume_id_hh_managed_resumes",
        "applications",
        "hh_managed_resumes",
        ["hh_managed_resume_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column("application_status_history", sa.Column("hh_apply_run_id", sa.Integer(), nullable=True))
    op.create_index(
        op.f("ix_application_status_history_hh_apply_run_id"),
        "application_status_history",
        ["hh_apply_run_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_application_status_history_hh_apply_run_id_hh_apply_runs",
        "application_status_history",
        "hh_apply_runs",
        ["hh_apply_run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_unique_constraint(
        "uq_application_status_history_hh_apply_run_id",
        "application_status_history",
        ["hh_apply_run_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_application_status_history_hh_apply_run_id", "application_status_history", type_="unique")
    op.drop_constraint("fk_application_status_history_hh_apply_run_id_hh_apply_runs", "application_status_history", type_="foreignkey")
    op.drop_index(op.f("ix_application_status_history_hh_apply_run_id"), table_name="application_status_history")
    op.drop_column("application_status_history", "hh_apply_run_id")

    op.drop_constraint("fk_applications_hh_managed_resume_id_hh_managed_resumes", "applications", type_="foreignkey")
    op.drop_constraint("fk_applications_last_hh_apply_run_id_hh_apply_runs", "applications", type_="foreignkey")
    op.drop_index(op.f("ix_applications_hh_managed_resume_id"), table_name="applications")
    op.drop_index(op.f("ix_applications_last_hh_apply_run_id"), table_name="applications")

    op.drop_column("applications", "last_external_apply_at")
    op.drop_column("applications", "external_apply_status")
    op.drop_column("applications", "hh_managed_resume_id")
    op.drop_column("applications", "last_hh_apply_run_id")
