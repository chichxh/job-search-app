"""create vacancy_parsed table

Revision ID: f2b4c6d8e0a1
Revises: e1f3a9b7c2d4
Create Date: 2026-02-26 13:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "f2b4c6d8e0a1"
down_revision: Union[str, Sequence[str], None] = "e1f3a9b7c2d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "vacancy_parsed",
        sa.Column("vacancy_id", sa.Integer(), nullable=False),
        sa.Column("plain_text", sa.Text(), nullable=False),
        sa.Column(
            "sections_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("quality_score", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.ForeignKeyConstraint(["vacancy_id"], ["vacancies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("vacancy_id"),
    )
    op.create_index("ix_vacancy_parsed_extracted_at", "vacancy_parsed", ["extracted_at"], unique=False)
    op.create_index("ix_vacancy_parsed_version", "vacancy_parsed", ["version"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_vacancy_parsed_version", table_name="vacancy_parsed")
    op.drop_index("ix_vacancy_parsed_extracted_at", table_name="vacancy_parsed")
    op.drop_table("vacancy_parsed")
