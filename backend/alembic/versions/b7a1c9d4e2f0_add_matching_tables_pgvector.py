"""add matching tables + pgvector

Revision ID: b7a1c9d4e2f0
Revises: 9f1a2b3c4d5e
Create Date: 2026-02-20 00:00:00.000000

"""

import os
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = "b7a1c9d4e2f0"
down_revision: Union[str, Sequence[str], None] = "9f1a2b3c4d5e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "384"))


def upgrade() -> None:
    # Включаем расширение для pgvector.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    op.create_table(
        "profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("resume_text", sa.Text(), nullable=False),
        sa.Column("skills_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_profiles_id"), "profiles", ["id"], unique=False)

    op.create_table(
        "vacancy_requirements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("vacancy_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("normalized_key", sa.String(length=255), nullable=True),
        sa.Column("weight", sa.Integer(), server_default="1", nullable=False),
        sa.Column("is_hard", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["vacancy_id"], ["vacancies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_vacancy_requirements_id"), "vacancy_requirements", ["id"], unique=False)
    op.create_index(op.f("ix_vacancy_requirements_vacancy_id"), "vacancy_requirements", ["vacancy_id"], unique=False)

    op.create_table(
        "resume_evidence",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("vacancy_id", sa.Integer(), nullable=False),
        sa.Column("requirement_id", sa.Integer(), nullable=True),
        sa.Column("evidence_text", sa.Text(), nullable=False),
        sa.Column("evidence_type", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requirement_id"], ["vacancy_requirements.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["vacancy_id"], ["vacancies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_resume_evidence_id"), "resume_evidence", ["id"], unique=False)
    op.create_index(op.f("ix_resume_evidence_profile_id"), "resume_evidence", ["profile_id"], unique=False)
    op.create_index(op.f("ix_resume_evidence_requirement_id"), "resume_evidence", ["requirement_id"], unique=False)
    op.create_index(op.f("ix_resume_evidence_vacancy_id"), "resume_evidence", ["vacancy_id"], unique=False)

    op.create_table(
        "vacancy_scores",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("vacancy_id", sa.Integer(), nullable=False),
        sa.Column("layer1_score", sa.Float(), nullable=False),
        sa.Column("layer2_score", sa.Float(), nullable=False),
        sa.Column("final_score", sa.Float(), nullable=False),
        sa.Column("verdict", sa.String(length=20), nullable=False),
        sa.Column("explanation", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["vacancy_id"], ["vacancies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", "vacancy_id", name="uq_vacancy_scores_profile_vacancy"),
    )
    op.create_index(op.f("ix_vacancy_scores_id"), "vacancy_scores", ["id"], unique=False)
    op.create_index(op.f("ix_vacancy_scores_profile_id"), "vacancy_scores", ["profile_id"], unique=False)
    op.create_index(op.f("ix_vacancy_scores_vacancy_id"), "vacancy_scores", ["vacancy_id"], unique=False)

    op.create_table(
        "vacancy_embeddings",
        sa.Column("vacancy_id", sa.Integer(), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["vacancy_id"], ["vacancies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("vacancy_id"),
    )

    op.create_table(
        "profile_embeddings",
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("profile_id"),
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_vacancy_embeddings_embedding_hnsw "
        "ON vacancy_embeddings USING hnsw (embedding vector_cosine_ops);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_profile_embeddings_embedding_hnsw "
        "ON profile_embeddings USING hnsw (embedding vector_cosine_ops);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_profile_embeddings_embedding_hnsw;")
    op.execute("DROP INDEX IF EXISTS ix_vacancy_embeddings_embedding_hnsw;")

    op.drop_table("profile_embeddings")
    op.drop_table("vacancy_embeddings")

    op.drop_index(op.f("ix_vacancy_scores_vacancy_id"), table_name="vacancy_scores")
    op.drop_index(op.f("ix_vacancy_scores_profile_id"), table_name="vacancy_scores")
    op.drop_index(op.f("ix_vacancy_scores_id"), table_name="vacancy_scores")
    op.drop_table("vacancy_scores")

    op.drop_index(op.f("ix_resume_evidence_vacancy_id"), table_name="resume_evidence")
    op.drop_index(op.f("ix_resume_evidence_requirement_id"), table_name="resume_evidence")
    op.drop_index(op.f("ix_resume_evidence_profile_id"), table_name="resume_evidence")
    op.drop_index(op.f("ix_resume_evidence_id"), table_name="resume_evidence")
    op.drop_table("resume_evidence")

    op.drop_index(op.f("ix_vacancy_requirements_vacancy_id"), table_name="vacancy_requirements")
    op.drop_index(op.f("ix_vacancy_requirements_id"), table_name="vacancy_requirements")
    op.drop_table("vacancy_requirements")

    op.drop_index(op.f("ix_profiles_id"), table_name="profiles")
    op.drop_table("profiles")
