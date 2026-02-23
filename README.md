# job-search-app

## HH clusters and extra params

- To preview HH facets (clusters), call `POST /api/v1/import/hh/clusters` with the same body as `/api/v1/import/hh` (`text` is required, plus optional `area`, etc.).
- The response contains `found`, HH `clusters`, and `applied_base_params`.
- Cluster items may include `params` parsed from HH `url`; send them back as `extra_params` in `/api/v1/import/hh` to narrow import results.
- `extra_params` supports values: `string`, `number`, `boolean`, `list[string|number]`, or `null`.

## Saved searches with extra HH filters

- Saved searches now store `filters_json` (JSONB) with additional HH query params (for example, `metro`, `professional_role`).
- New API endpoints under `/api/v1/saved-searches`:
  - `POST /saved-searches`
  - `GET /saved-searches`
  - `PATCH /saved-searches/{id}`
  - `POST /saved-searches/{id}/sync`
  - `GET /saved-searches/{id}/clusters`
- Periodic Celery sync uses `filters_json` from `saved_searches` when requesting HH vacancies.

## Миграции в контейнере

- `docker compose exec api alembic revision --autogenerate -m "add matching tables"`
- `docker compose exec api alembic upgrade head`

## Embeddings (Celery)

- Провайдер задаётся env: `EMBEDDING_PROVIDER` (`local`), `EMBEDDING_MODEL` (`all-MiniLM-L6-v2`), `EMBEDDING_DIM` (`384`).
- При сохранении/обновлении вакансий и профилей ставятся Celery-задачи на пересчёт embedding.
- Dev endpoint для массового пересчёта: `POST /api/v1/dev/embeddings/rebuild-vacancies?limit=20`.

## Frontend (Vite)

- Install dependencies: `cd frontend && npm install`.
- Start frontend in dev mode: `npm run dev`.
- By default, Vite proxies `/api/*` to `VITE_API_PROXY_TARGET` (default `http://127.0.0.1:8000`) from `frontend/vite.config.js`.
- Optional env var `VITE_API_BASE_URL` can be set to call API directly (for example `http://localhost:8000`) and bypass the relative base URL.

Examples:

```bash
# 1) Run with proxy (recommended for local dev)
cd frontend
VITE_API_PROXY_TARGET=http://127.0.0.1:8000 npm run dev

# 2) Run with explicit API base URL
cd frontend
VITE_API_BASE_URL=http://127.0.0.1:8000 npm run dev
```
