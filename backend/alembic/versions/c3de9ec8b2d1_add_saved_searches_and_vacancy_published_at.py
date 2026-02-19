"""add saved searches and vacancy published at

Revision ID: c3de9ec8b2d1
Revises: 835e5f5bd0c3
Create Date: 2026-02-19 09:15:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c3de9ec8b2d1"
down_revision: Union[str, Sequence[str], None] = "835e5f5bd0c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("vacancies", sa.Column("published_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "saved_searches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("text", sa.String(length=255), nullable=False),
        sa.Column("area", sa.String(length=50), nullable=True),
        sa.Column("schedule", sa.String(length=50), nullable=True),
        sa.Column("experience", sa.String(length=50), nullable=True),
        sa.Column("salary_from", sa.Integer(), nullable=True),
        sa.Column("salary_to", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=True),
        sa.Column("per_page", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("pages_limit", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("cursor_page", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_saved_searches_id"), "saved_searches", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_saved_searches_id"), table_name="saved_searches")
    op.drop_table("saved_searches")
    op.drop_column("vacancies", "published_at")
