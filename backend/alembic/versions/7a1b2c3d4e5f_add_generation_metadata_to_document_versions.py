"""add generation metadata to document versions

Revision ID: 7a1b2c3d4e5f
Revises: 4e2b7c9d1a6f
Create Date: 2026-03-26 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "7a1b2c3d4e5f"
down_revision: Union[str, Sequence[str], None] = "4e2b7c9d1a6f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "resume_versions",
        sa.Column("generation_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "cover_letter_versions",
        sa.Column("generation_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("cover_letter_versions", "generation_metadata")
    op.drop_column("resume_versions", "generation_metadata")
