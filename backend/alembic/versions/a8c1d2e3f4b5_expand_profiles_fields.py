"""expand profiles fields

Revision ID: a8c1d2e3f4b5
Revises: f2b4c6d8e0a1
Create Date: 2026-02-27 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "a8c1d2e3f4b5"
down_revision: Union[str, Sequence[str], None] = "f2b4c6d8e0a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("profiles", sa.Column("full_name", sa.String(length=255), nullable=True))
    op.add_column("profiles", sa.Column("email", sa.String(length=255), nullable=True))
    op.add_column("profiles", sa.Column("phone", sa.String(length=50), nullable=True))
    op.add_column("profiles", sa.Column("telegram", sa.String(length=255), nullable=True))

    op.add_column("profiles", sa.Column("city", sa.String(length=255), nullable=True))
    op.add_column("profiles", sa.Column("country", sa.String(length=255), nullable=True))
    op.add_column("profiles", sa.Column("metro", sa.String(length=255), nullable=True))

    op.add_column("profiles", sa.Column("citizenship", sa.String(length=255), nullable=True))
    op.add_column("profiles", sa.Column("work_authorization_country", sa.String(length=255), nullable=True))
    op.add_column("profiles", sa.Column("needs_sponsorship", sa.Boolean(), nullable=False, server_default="false"))

    op.add_column("profiles", sa.Column("available_from", sa.Date(), nullable=True))
    op.add_column("profiles", sa.Column("notice_period_days", sa.Integer(), nullable=True))

    op.add_column("profiles", sa.Column("preferred_employment", sa.String(length=50), nullable=True))
    op.add_column("profiles", sa.Column("preferred_schedule", sa.String(length=50), nullable=True))

    op.add_column(
        "profiles",
        sa.Column("preferred_industries", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
    )
    op.add_column(
        "profiles",
        sa.Column("preferred_company_types", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
    )
    op.add_column(
        "profiles",
        sa.Column("interest_tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
    )
    op.add_column(
        "profiles",
        sa.Column("preferred_tech", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
    )
    op.add_column(
        "profiles",
        sa.Column("excluded_tech", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
    )
    op.add_column(
        "profiles",
        sa.Column("team_preferences_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
    )

    op.add_column("profiles", sa.Column("summary_about", sa.Text(), nullable=True))
    op.add_column("profiles", sa.Column("seniority_level", sa.String(length=50), nullable=True))
    op.add_column("profiles", sa.Column("years_total", sa.Float(), nullable=True))

    op.add_column(
        "profiles",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_column("profiles", "updated_at")
    op.drop_column("profiles", "years_total")
    op.drop_column("profiles", "seniority_level")
    op.drop_column("profiles", "summary_about")
    op.drop_column("profiles", "team_preferences_json")
    op.drop_column("profiles", "excluded_tech")
    op.drop_column("profiles", "preferred_tech")
    op.drop_column("profiles", "interest_tags")
    op.drop_column("profiles", "preferred_company_types")
    op.drop_column("profiles", "preferred_industries")
    op.drop_column("profiles", "preferred_schedule")
    op.drop_column("profiles", "preferred_employment")
    op.drop_column("profiles", "notice_period_days")
    op.drop_column("profiles", "available_from")
    op.drop_column("profiles", "needs_sponsorship")
    op.drop_column("profiles", "work_authorization_country")
    op.drop_column("profiles", "citizenship")
    op.drop_column("profiles", "metro")
    op.drop_column("profiles", "country")
    op.drop_column("profiles", "city")
    op.drop_column("profiles", "telegram")
    op.drop_column("profiles", "phone")
    op.drop_column("profiles", "email")
    op.drop_column("profiles", "full_name")
