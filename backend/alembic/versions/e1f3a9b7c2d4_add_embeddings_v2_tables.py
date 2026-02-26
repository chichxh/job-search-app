"""add embeddings v2 tables

Revision ID: e1f3a9b7c2d4
Revises: d4f8a2c1e6b7
Create Date: 2026-02-26 12:50:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = "e1f3a9b7c2d4"
down_revision: Union[str, Sequence[str], None] = "d4f8a2c1e6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIM = 384


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    op.create_table(
        "vacancy_embeddings_v2",
        sa.Column("vacancy_id", sa.Integer(), sa.ForeignKey("vacancies.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "profile_embeddings_v2",
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_vacancy_embeddings_v2_embedding_hnsw "
        "ON vacancy_embeddings_v2 USING hnsw (embedding vector_cosine_ops);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_profile_embeddings_v2_embedding_hnsw "
        "ON profile_embeddings_v2 USING hnsw (embedding vector_cosine_ops);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_profile_embeddings_v2_embedding_hnsw;")
    op.execute("DROP INDEX IF EXISTS ix_vacancy_embeddings_v2_embedding_hnsw;")
    op.drop_table("profile_embeddings_v2")
    op.drop_table("vacancy_embeddings_v2")
