#!/usr/bin/env python3
"""Safety checks for Alembic migration state.

Usage:
  python scripts/verify_migrations.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import NullPool
from alembic.runtime.migration import MigrationContext


def _is_truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _mask_url(raw_url: str) -> str:
    from sqlalchemy.engine import make_url

    try:
        return make_url(raw_url).render_as_string(hide_password=True)
    except Exception:
        return "<hidden>"


def main() -> int:
    backend_root = Path(__file__).resolve().parents[1]
    alembic_ini = backend_root / "alembic.ini"

    if not alembic_ini.exists():
        print(f"❌ alembic.ini not found: {alembic_ini}")
        return 2

    cfg = Config(str(alembic_ini))

    # env.py already supports DATABASE_URL override; we do the same for explicit logging.
    database_url = os.getenv("DATABASE_URL") or cfg.get_main_option("sqlalchemy.url")
    if not database_url:
        print("❌ DATABASE_URL is empty and sqlalchemy.url is not set in alembic.ini")
        return 2

    cfg.set_main_option("sqlalchemy.url", database_url)

    print(f"ℹ️ Using database: {_mask_url(database_url)}")

    # 1) DB accessibility check
    try:
        engine = create_engine(database_url, poolclass=NullPool)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        print("✅ Database is reachable")
    except SQLAlchemyError as exc:
        print(f"❌ Database check failed: {exc}")
        return 1

    # 2) Upgrade to head (detect broken migrations)
    try:
        command.upgrade(cfg, "head")
        print("✅ alembic upgrade head completed")
    except Exception as exc:  # noqa: BLE001 - we want to surface any migration failure
        print(f"❌ alembic upgrade head failed: {exc}")
        return 1

    # 3) Current heads state check
    script = ScriptDirectory.from_config(cfg)
    expected_heads = tuple(script.get_heads())
    expected_heads_set = set(expected_heads)

    allow_multiple_heads = _is_truthy(os.getenv("ALLOW_MULTIPLE_ALEMBIC_HEADS"))
    if len(expected_heads) > 1 and not allow_multiple_heads:
        print("❌ Multiple Alembic heads detected in code repository:")
        for rev in expected_heads:
            print(f"   - {rev}")
        print(
            "   Resolve by creating a merge migration (alembic merge ...) "
            "or set ALLOW_MULTIPLE_ALEMBIC_HEADS=1 with documented justification."
        )
        return 1

    if len(expected_heads) > 1:
        print("⚠️ Multiple heads are allowed by ALLOW_MULTIPLE_ALEMBIC_HEADS=1")

    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            current_heads = tuple(context.get_current_heads())
    except SQLAlchemyError as exc:
        print(f"❌ Failed to read current migration revision from DB: {exc}")
        return 1

    current_heads_set = set(current_heads)

    print(f"ℹ️ Repo heads: {sorted(expected_heads_set)}")
    print(f"ℹ️ DB current: {sorted(current_heads_set)}")

    if current_heads_set != expected_heads_set:
        print("❌ Migration mismatch: DB current revision set does not match repo heads")
        print("   Run `alembic upgrade head` and re-check. If mismatch persists, inspect migration history.")
        return 1

    print("✅ Migration state is consistent (current == heads)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
