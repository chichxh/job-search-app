"""add profile normalized tables

Revision ID: 3c9e1f7a2b4d
Revises: a8c1d2e3f4b5
Create Date: 2026-02-27 00:00:01.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3c9e1f7a2b4d"
down_revision: Union[str, Sequence[str], None] = "a8c1d2e3f4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "profile_experiences",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("position_title", sa.String(length=255), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("responsibilities_text", sa.Text(), nullable=False),
        sa.Column("achievements_text", sa.Text(), nullable=False),
        sa.Column("tech_stack_text", sa.Text(), nullable=True),
        sa.Column("employment_type", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_profile_experiences_id"), "profile_experiences", ["id"], unique=False)
    op.create_index(op.f("ix_profile_experiences_profile_id"), "profile_experiences", ["profile_id"], unique=False)

    op.create_table(
        "profile_projects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=255), nullable=True),
        sa.Column("description_text", sa.Text(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("tech_stack_text", sa.Text(), nullable=True),
        sa.Column("url", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_profile_projects_id"), "profile_projects", ["id"], unique=False)
    op.create_index(op.f("ix_profile_projects_profile_id"), "profile_projects", ["profile_id"], unique=False)

    op.create_table(
        "profile_achievements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description_text", sa.Text(), nullable=False),
        sa.Column("metric", sa.String(length=100), nullable=True),
        sa.Column("achieved_at", sa.Date(), nullable=True),
        sa.Column("related_experience_id", sa.Integer(), nullable=True),
        sa.Column("related_project_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["related_experience_id"], ["profile_experiences.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["related_project_id"], ["profile_projects.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_profile_achievements_id"), "profile_achievements", ["id"], unique=False)
    op.create_index(op.f("ix_profile_achievements_profile_id"), "profile_achievements", ["profile_id"], unique=False)
    op.create_index(
        op.f("ix_profile_achievements_related_experience_id"),
        "profile_achievements",
        ["related_experience_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_profile_achievements_related_project_id"),
        "profile_achievements",
        ["related_project_id"],
        unique=False,
    )

    op.create_table(
        "profile_education",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("institution", sa.String(length=255), nullable=False),
        sa.Column("degree_level", sa.String(length=100), nullable=False),
        sa.Column("field_of_study", sa.String(length=255), nullable=False),
        sa.Column("start_year", sa.Integer(), nullable=True),
        sa.Column("end_year", sa.Integer(), nullable=True),
        sa.Column("description_text", sa.Text(), nullable=True),
        sa.Column("gpa", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_profile_education_id"), "profile_education", ["id"], unique=False)
    op.create_index(op.f("ix_profile_education_profile_id"), "profile_education", ["profile_id"], unique=False)

    op.create_table(
        "profile_certificates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("issuer", sa.String(length=255), nullable=False),
        sa.Column("issued_at", sa.Date(), nullable=True),
        sa.Column("expires_at", sa.Date(), nullable=True),
        sa.Column("url", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_profile_certificates_id"), "profile_certificates", ["id"], unique=False)
    op.create_index(op.f("ix_profile_certificates_profile_id"), "profile_certificates", ["profile_id"], unique=False)

    op.create_table(
        "profile_skills",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("name_raw", sa.String(length=255), nullable=False),
        sa.Column("normalized_key", sa.String(length=255), nullable=True),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("level", sa.String(length=50), nullable=False),
        sa.Column("years", sa.Float(), nullable=True),
        sa.Column("last_used_year", sa.Integer(), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("evidence_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_profile_skills_id"), "profile_skills", ["id"], unique=False)
    op.create_index(op.f("ix_profile_skills_normalized_key"), "profile_skills", ["normalized_key"], unique=False)
    op.create_index(op.f("ix_profile_skills_profile_id"), "profile_skills", ["profile_id"], unique=False)

    op.create_table(
        "profile_languages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("language", sa.String(length=100), nullable=False),
        sa.Column("level", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_profile_languages_id"), "profile_languages", ["id"], unique=False)
    op.create_index(op.f("ix_profile_languages_profile_id"), "profile_languages", ["profile_id"], unique=False)

    op.create_table(
        "profile_links",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("url", sa.String(length=1024), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_profile_links_id"), "profile_links", ["id"], unique=False)
    op.create_index(op.f("ix_profile_links_profile_id"), "profile_links", ["profile_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_profile_links_profile_id"), table_name="profile_links")
    op.drop_index(op.f("ix_profile_links_id"), table_name="profile_links")
    op.drop_table("profile_links")

    op.drop_index(op.f("ix_profile_languages_profile_id"), table_name="profile_languages")
    op.drop_index(op.f("ix_profile_languages_id"), table_name="profile_languages")
    op.drop_table("profile_languages")

    op.drop_index(op.f("ix_profile_skills_profile_id"), table_name="profile_skills")
    op.drop_index(op.f("ix_profile_skills_normalized_key"), table_name="profile_skills")
    op.drop_index(op.f("ix_profile_skills_id"), table_name="profile_skills")
    op.drop_table("profile_skills")

    op.drop_index(op.f("ix_profile_certificates_profile_id"), table_name="profile_certificates")
    op.drop_index(op.f("ix_profile_certificates_id"), table_name="profile_certificates")
    op.drop_table("profile_certificates")

    op.drop_index(op.f("ix_profile_education_profile_id"), table_name="profile_education")
    op.drop_index(op.f("ix_profile_education_id"), table_name="profile_education")
    op.drop_table("profile_education")

    op.drop_index(op.f("ix_profile_achievements_related_project_id"), table_name="profile_achievements")
    op.drop_index(op.f("ix_profile_achievements_related_experience_id"), table_name="profile_achievements")
    op.drop_index(op.f("ix_profile_achievements_profile_id"), table_name="profile_achievements")
    op.drop_index(op.f("ix_profile_achievements_id"), table_name="profile_achievements")
    op.drop_table("profile_achievements")

    op.drop_index(op.f("ix_profile_projects_profile_id"), table_name="profile_projects")
    op.drop_index(op.f("ix_profile_projects_id"), table_name="profile_projects")
    op.drop_table("profile_projects")

    op.drop_index(op.f("ix_profile_experiences_profile_id"), table_name="profile_experiences")
    op.drop_index(op.f("ix_profile_experiences_id"), table_name="profile_experiences")
    op.drop_table("profile_experiences")
