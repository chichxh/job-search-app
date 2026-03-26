# Migrations verification (Alembic)

## Quick check (recommended)

From repository root:

```bash
docker compose -f infra/docker-compose.yml exec api python scripts/verify_migrations.py
```

The helper verifies:
- database is reachable;
- `alembic upgrade head` succeeds;
- database `current` revision set equals repository `heads`;
- repository does not have multiple heads (unless explicitly allowed).

## Local run without Docker

From `backend/`:

```bash
python scripts/verify_migrations.py
```

`DATABASE_URL` can override `alembic.ini` connection settings.

## If `current != heads`

1. Run `alembic upgrade head` again.
2. Check `alembic current` and `alembic heads`.
3. If there are multiple heads, create merge migration (`alembic merge ...`) and document why.

## About multiple heads

By default, helper fails when multiple repository heads are detected.

Temporary override (only with explicit documented reason):

```bash
ALLOW_MULTIPLE_ALEMBIC_HEADS=1 python scripts/verify_migrations.py
```

## Do **not** use `alembic stamp head` as a quick fix

`alembic stamp head` does not execute migrations; it only rewrites version marker.
Use it only for controlled recovery scenarios when real schema state is already aligned and manually verified.
