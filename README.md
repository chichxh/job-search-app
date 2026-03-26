# job-search-app

## Verification

Минимальный воспроизводимый smoke-check для базовой версии: `verification-checklist.md`.
Для reproducible проверки parsing+matching quality: `backend/docs/matching_diagnostics_verification.md`.

## Current status (implemented vs planned)

### LLM providers

- ✅ `gigachat` — implemented and used by document generation/tailoring flows.
- 🟡 `openai` — **planned, not implemented**. In current code path this provider raises `NotImplementedError`.

### Embedding providers

- ✅ `fastembed` — implemented (CPU ONNX).
- ✅ `localhash` — implemented (lightweight hashing baseline).
- 🟡 `openai` — **planned, not implemented** (stub).
- 🟡 `gigachat` — **planned, not implemented** (stub).

Planned directions remain in repository, but only providers marked as implemented above are production-ready today.

## Demo-ready / supported flow

Current end-to-end flow that is supported by existing API/backend logic:

1. Create/update a profile (`/api/v1/profiles`, plus profile data CRUD).
2. Import vacancies from HH (`/api/v1/import/hh`).
3. Run parsing/embeddings/matching pipeline (background tasks + recommendations endpoints).
4. Fetch recommendations and vacancy matching details.
5. Fetch tailoring output for profile-vacancy pair.
6. Generate draft resume and draft cover letter via:
   - `POST /api/v1/profiles/{profile_id}/vacancies/{vacancy_id}/resume/generate`
   - `POST /api/v1/profiles/{profile_id}/vacancies/{vacancy_id}/cover-letter/generate`

## Demo flow (manual, UI)

Ниже — актуальный ручной сценарий проверки demo-flow в текущем UI:

1. **Profile setup**: откройте `/settings`, заполните профиль и нажмите сохранение.
2. **HH import**: откройте `/vacancies`, нажмите **«Выгрузить вакансии из HH»** и дождитесь статуса успешного импорта.
3. **Recommendations recompute**: перейдите на `/recommendations`, нажмите **«Пересчитать рекомендации»** и дождитесь `SUCCESS`.
4. **Open vacancy details**: откройте вакансию из списка рекомендаций (переход на `/vacancies/:vacancyId`).
5. **Tailoring check**: на странице вакансии проверьте блок **Мэтчинг** (tailoring).
6. **Generate drafts**: в блоке **Document generation** нажмите:
   - `Generate resume draft`
   - `Generate cover letter draft`
7. **Approve**: в vacancy-scoped списках документов для этой вакансии нажмите:
   - `Approve resume` для draft resume
   - `Approve cover letter` для draft cover letter
8. **Fallback editor (optional)**: при необходимости углублённого редактирования используйте ссылку **Open full editor in Settings**.

### Manual verification checklist

- [ ] Profile save (`/settings`)
- [ ] HH import (`/vacancies`)
- [ ] Recommendations recompute (`/recommendations`)
- [ ] Open vacancy details (`/vacancies/:vacancyId`)
- [ ] Load tailoring (блок **Мэтчинг**)
- [ ] Generate resume draft
- [ ] Generate cover letter draft
- [ ] Approve generated document

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

- Провайдер задаётся env: `EMBEDDING_PROVIDER` (`fastembed` | `localhash`), по умолчанию `fastembed`.
- Для `fastembed` используется CPU-only ONNX модель `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (RU/EN). Имя можно переопределить через `FASTEMBED_MODEL_NAME` или `EMBEDDING_MODEL_NAME`.
- `EMBEDDING_DIM` можно не задавать: приложение автоматически берёт размерность из модели (`384` для `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`) и подставляет её в runtime.
- Если `EMBEDDING_DIM` задан и не совпадает с размерностью модели, API/worker падают при старте с понятной ошибкой конфигурации.
- При сохранении/обновлении вакансий и профилей ставятся Celery-задачи на пересчёт embedding.
- Dev endpoints для массового пересчёта c очисткой старых векторов: `POST /api/v1/dev/embeddings/rebuild-vacancies?limit=20`, `POST /api/v1/dev/embeddings/rebuild-profiles?limit=20`, `POST /api/v1/dev/embeddings/rebuild-profile/1`.
- Dev diagnostics endpoints для quality snapshot:
  - `GET /dev/matching/diagnostics` (global quality summary)
  - `GET /dev/matching/diagnostics?profile_id=1&top_n=10` (global + profile summary)
  - `GET /dev/profiles/1/matching/diagnostics?top_n=10` (profile-only breakdown)

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

## LLM configuration (env)

- `LLM_PROVIDER`: `gigachat` | `openai` (default `gigachat`).
  - `gigachat` — implemented.
  - `openai` — planned / not implemented yet.
- `LLM_MODEL`: model name (default `GigaChat`), например `GigaChat` или `GigaChat-Pro`.
- `LLM_TEMPERATURE`: float (default `0.2`).
- `LLM_MAX_TOKENS`: int (default `1200`).
- `GIGACHAT_AUTH_KEY`: required when `LLM_PROVIDER=gigachat`.
- `GIGACHAT_SCOPE`: default `GIGACHAT_API_PERS`.
- `GIGACHAT_OAUTH_URL`: default `https://ngw.devices.sberbank.ru:9443/api/v2/oauth`.
- `GIGACHAT_API_BASE`: default `https://gigachat.devices.sberbank.ru`.
- `GIGACHAT_VERIFY_SSL`: bool, default `true`.

Пример env для GigaChat:

```env
LLM_PROVIDER=gigachat
LLM_MODEL=GigaChat
GIGACHAT_AUTH_KEY=...
GIGACHAT_SCOPE=GIGACHAT_API_PERS
GIGACHAT_OAUTH_URL=https://ngw.devices.sberbank.ru:9443/api/v2/oauth
GIGACHAT_API_BASE=https://gigachat.devices.sberbank.ru
```

Validation helper: `app.core.config.validate_llm_settings()`.

- App startup does **not** require `GIGACHAT_AUTH_KEY`.
- Clear error is raised only when LLM settings are validated/used and required key is missing.

Проверка генерации документов (после импорта вакансий/профиля и при наличии `profile_id` + `vacancy_id`):

```bash
# Generate resume draft
curl -X POST "http://127.0.0.1:8000/api/v1/profiles/<profile_id>/vacancies/<vacancy_id>/resume/generate"

# Generate cover letter draft
curl -X POST "http://127.0.0.1:8000/api/v1/profiles/<profile_id>/vacancies/<vacancy_id>/cover-letter/generate"
```
