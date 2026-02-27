"""add resume and cover letter versions

Revision ID: 4e2b7c9d1a6f
Revises: 3c9e1f7a2b4d
Create Date: 2026-02-27 00:00:02.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4e2b7c9d1a6f"
down_revision: Union[str, Sequence[str], None] = "3c9e1f7a2b4d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "resume_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("vacancy_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("format", sa.String(length=20), nullable=False, server_default="plain"),
        sa.Column("source", sa.String(length=20), nullable=False, server_default="user"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["vacancy_id"], ["vacancies.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_resume_versions_id"), "resume_versions", ["id"], unique=False)
    op.create_index(op.f("ix_resume_versions_profile_id"), "resume_versions", ["profile_id"], unique=False)
    op.create_index(op.f("ix_resume_versions_vacancy_id"), "resume_versions", ["vacancy_id"], unique=False)
    op.create_index("ix_resume_versions_profile_status", "resume_versions", ["profile_id", "status"], unique=False)
    op.create_index("ix_resume_versions_profile_vacancy", "resume_versions", ["profile_id", "vacancy_id"], unique=False)

    op.create_table(
        "cover_letter_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("vacancy_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("subject", sa.String(length=255), nullable=True),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False, server_default="user"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["vacancy_id"], ["vacancies.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_cover_letter_versions_id"), "cover_letter_versions", ["id"], unique=False)
    op.create_index(
        op.f("ix_cover_letter_versions_profile_id"), "cover_letter_versions", ["profile_id"], unique=False
    )
    op.create_index(
        op.f("ix_cover_letter_versions_vacancy_id"), "cover_letter_versions", ["vacancy_id"], unique=False
    )
    op.create_index(
        "ix_cover_letter_versions_profile_status", "cover_letter_versions", ["profile_id", "status"], unique=False
    )
    op.create_index(
        "ix_cover_letter_versions_profile_vacancy",
        "cover_letter_versions",
        ["profile_id", "vacancy_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_cover_letter_versions_profile_vacancy", table_name="cover_letter_versions")
    op.drop_index("ix_cover_letter_versions_profile_status", table_name="cover_letter_versions")
    op.drop_index(op.f("ix_cover_letter_versions_vacancy_id"), table_name="cover_letter_versions")
    op.drop_index(op.f("ix_cover_letter_versions_profile_id"), table_name="cover_letter_versions")
    op.drop_index(op.f("ix_cover_letter_versions_id"), table_name="cover_letter_versions")
    op.drop_table("cover_letter_versions")

    op.drop_index("ix_resume_versions_profile_vacancy", table_name="resume_versions")
    op.drop_index("ix_resume_versions_profile_status", table_name="resume_versions")
    op.drop_index(op.f("ix_resume_versions_vacancy_id"), table_name="resume_versions")
    op.drop_index(op.f("ix_resume_versions_profile_id"), table_name="resume_versions")
    op.drop_index(op.f("ix_resume_versions_id"), table_name="resume_versions")
    op.drop_table("resume_versions")
