"""add hh oauth connections

Revision ID: 6b9c2f1d7e8a
Revises: 2b7d4e1a9c3f
Create Date: 2026-03-26 13:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6b9c2f1d7e8a"
down_revision: Union[str, Sequence[str], None] = "2b7d4e1a9c3f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "hh_oauth_connections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False, server_default="hh"),
        sa.Column("access_token", sa.Text(), nullable=False),
        sa.Column("refresh_token", sa.Text(), nullable=True),
        sa.Column("token_type", sa.String(length=32), nullable=True),
        sa.Column("scope", sa.Text(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("hh_user_id", sa.String(length=64), nullable=True),
        sa.Column("hh_email", sa.String(length=255), nullable=True),
        sa.Column("hh_resume_id", sa.String(length=64), nullable=True),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_imported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "provider", name="uq_hh_oauth_connections_user_provider"),
    )
    op.create_index("ix_hh_oauth_connections_id", "hh_oauth_connections", ["id"], unique=False)
    op.create_index("ix_hh_oauth_connections_user_id", "hh_oauth_connections", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_hh_oauth_connections_user_id", table_name="hh_oauth_connections")
    op.drop_index("ix_hh_oauth_connections_id", table_name="hh_oauth_connections")
    op.drop_table("hh_oauth_connections")
