"""merge heads 1c2d3e4f5a6b and 6b9c2f1d7e8a

Revision ID: 95eaf9c66405
Revises: 1c2d3e4f5a6b, 6b9c2f1d7e8a
Create Date: 2026-03-26 21:09:36.886311

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '95eaf9c66405'
down_revision: Union[str, Sequence[str], None] = ('1c2d3e4f5a6b', '6b9c2f1d7e8a')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
