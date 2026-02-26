"""add profile cutoff fields

Revision ID: d4f8a2c1e6b7
Revises: b7a1c9d4e2f0
Create Date: 2026-02-26 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d4f8a2c1e6b7"
down_revision: Union[str, Sequence[str], None] = "b7a1c9d4e2f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("profiles", sa.Column("location", sa.String(length=255), nullable=True))
    op.add_column("profiles", sa.Column("remote_ok", sa.Boolean(), server_default="true", nullable=False))
    op.add_column("profiles", sa.Column("relocation_ok", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("profiles", sa.Column("salary_min", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("profiles", "salary_min")
    op.drop_column("profiles", "relocation_ok")
    op.drop_column("profiles", "remote_ok")
    op.drop_column("profiles", "location")
