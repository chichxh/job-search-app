"""expand profile language level length

Revision ID: 5d6e7f8a9b0c
Revises: 1c2d3e4f5a6b
Create Date: 2026-03-29 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5d6e7f8a9b0c"
down_revision: Union[str, Sequence[str], None] = "1c2d3e4f5a6b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "profile_languages",
        "level",
        existing_type=sa.String(length=20),
        type_=sa.String(length=64),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "profile_languages",
        "level",
        existing_type=sa.String(length=64),
        type_=sa.String(length=20),
        existing_nullable=False,
    )
