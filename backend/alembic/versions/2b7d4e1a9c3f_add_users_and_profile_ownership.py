"""add users and profile ownership

Revision ID: 2b7d4e1a9c3f
Revises: f2b4c6d8e0a1
Create Date: 2026-03-26 10:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2b7d4e1a9c3f"
down_revision: Union[str, Sequence[str], None] = "f2b4c6d8e0a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_id", "users", ["id"], unique=False)
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.add_column("profiles", sa.Column("user_id", sa.Integer(), nullable=True))

    connection.execute(
        sa.text("INSERT INTO users (email, password_hash, is_active) VALUES (:email, :password_hash, true)"),
        {
            "email": "demo@example.local",
            "password_hash": "pbkdf2_sha256$120000$fe9f4285820b62acfe810482c1654ae7$800e74c8a32c5cee937b3afa01e01ca96f90bad89f7104d317e012423a436125",
        },
    )
    connection.execute(
        sa.text("UPDATE profiles SET user_id = (SELECT id FROM users WHERE email = :email)"),
        {"email": "demo@example.local"},
    )

    op.alter_column("profiles", "user_id", nullable=False)
    op.create_index("ix_profiles_user_id", "profiles", ["user_id"], unique=False)
    op.create_foreign_key("fk_profiles_user_id_users", "profiles", "users", ["user_id"], ["id"], ondelete="CASCADE")


def downgrade() -> None:
    op.drop_constraint("fk_profiles_user_id_users", "profiles", type_="foreignkey")
    op.drop_index("ix_profiles_user_id", table_name="profiles")
    op.drop_column("profiles", "user_id")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_id", table_name="users")
    op.drop_table("users")
