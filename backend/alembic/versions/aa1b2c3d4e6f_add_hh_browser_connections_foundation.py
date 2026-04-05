"""add hh browser connections foundation

Revision ID: aa1b2c3d4e6f
Revises: 95eaf9c66405, 5d6e7f8a9b0c
Create Date: 2026-04-05 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "aa1b2c3d4e6f"
down_revision: Union[str, Sequence[str], None] = ("95eaf9c66405", "5d6e7f8a9b0c")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "hh_browser_connections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="disconnected"),
        sa.Column("requires_reauth", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_authenticated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("session_state_ref", sa.String(length=255), nullable=True),
        sa.Column("session_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=64), nullable=True),
        sa.Column("last_error_message", sa.String(length=160), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_hh_browser_connections_user_id"),
    )
    op.create_index("ix_hh_browser_connections_id", "hh_browser_connections", ["id"], unique=False)
    op.create_index("ix_hh_browser_connections_user_id", "hh_browser_connections", ["user_id"], unique=False)
    op.create_index("ix_hh_browser_connections_status", "hh_browser_connections", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_hh_browser_connections_status", table_name="hh_browser_connections")
    op.drop_index("ix_hh_browser_connections_user_id", table_name="hh_browser_connections")
    op.drop_index("ix_hh_browser_connections_id", table_name="hh_browser_connections")
    op.drop_table("hh_browser_connections")
