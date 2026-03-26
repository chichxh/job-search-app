"""add applications funnel tables

Revision ID: 1c2d3e4f5a6b
Revises: 7a1b2c3d4e5f
Create Date: 2026-03-26 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "1c2d3e4f5a6b"
down_revision: Union[str, Sequence[str], None] = "7a1b2c3d4e5f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


APPLICATION_STATUS_VALUES = [
    "saved",
    "planned",
    "applied",
    "hr_screen",
    "tech_interview",
    "test_task",
    "offer",
    "rejected",
    "archived",
]


def upgrade() -> None:
    op.create_table(
        "applications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("vacancy_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="saved"),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("resume_version_id", sa.Integer(), nullable=True),
        sa.Column("cover_letter_version_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            f"status IN ({', '.join([repr(value) for value in APPLICATION_STATUS_VALUES])})",
            name="ck_applications_status",
        ),
        sa.ForeignKeyConstraint(["cover_letter_version_id"], ["cover_letter_versions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resume_version_id"], ["resume_versions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["vacancy_id"], ["vacancies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", "vacancy_id", name="uq_applications_profile_vacancy"),
    )
    op.create_index("ix_applications_id", "applications", ["id"], unique=False)
    op.create_index("ix_applications_profile_id", "applications", ["profile_id"], unique=False)
    op.create_index("ix_applications_vacancy_id", "applications", ["vacancy_id"], unique=False)
    op.create_index("ix_applications_resume_version_id", "applications", ["resume_version_id"], unique=False)
    op.create_index(
        "ix_applications_cover_letter_version_id",
        "applications",
        ["cover_letter_version_id"],
        unique=False,
    )
    op.create_index("ix_applications_updated_at", "applications", ["updated_at"], unique=False)

    op.create_table(
        "application_status_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=True),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            f"to_status IN ({', '.join([repr(value) for value in APPLICATION_STATUS_VALUES])})",
            name="ck_application_status_history_to_status",
        ),
        sa.CheckConstraint(
            f"from_status IS NULL OR from_status IN ({', '.join([repr(value) for value in APPLICATION_STATUS_VALUES])})",
            name="ck_application_status_history_from_status",
        ),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_application_status_history_id", "application_status_history", ["id"], unique=False)
    op.create_index(
        "ix_application_status_history_application_id",
        "application_status_history",
        ["application_id"],
        unique=False,
    )
    op.create_index(
        "ix_application_status_history_created_at",
        "application_status_history",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_application_status_history_created_at", table_name="application_status_history")
    op.drop_index("ix_application_status_history_application_id", table_name="application_status_history")
    op.drop_index("ix_application_status_history_id", table_name="application_status_history")
    op.drop_table("application_status_history")

    op.drop_index("ix_applications_updated_at", table_name="applications")
    op.drop_index("ix_applications_cover_letter_version_id", table_name="applications")
    op.drop_index("ix_applications_resume_version_id", table_name="applications")
    op.drop_index("ix_applications_vacancy_id", table_name="applications")
    op.drop_index("ix_applications_profile_id", table_name="applications")
    op.drop_index("ix_applications_id", table_name="applications")
    op.drop_table("applications")
