"""add hh resume auto-hide policy fields

Revision ID: ab12cd34ef56
Revises: f6a1b2c3d4e5
Create Date: 2026-04-05 00:45:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "ab12cd34ef56"
down_revision: Union[str, Sequence[str], None] = "f6a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "hh_managed_resumes",
        sa.Column("auto_hide_from_all_enabled", sa.Boolean(), nullable=False, server_default="true"),
    )


def downgrade() -> None:
    op.drop_column("hh_managed_resumes", "auto_hide_from_all_enabled")
