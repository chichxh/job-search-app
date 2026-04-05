# job-search-app

## Verification

## Testing

Минимальный backend smoke/integration suite и инструкции запуска: `TESTING.md`.
Операционная памятка по наблюдаемости фоновых задач: `backend/docs/background_tasks_observability.md`.
Короткий reproducible runbook запуска/health/smoke: `backend/docs/operational_runbook.md`.
Там же добавлен раздел HH automation diagnostics/troubleshooting (`/integrations/hh-browser/diagnostics`).
Документация по Auth MVP (JWT + user↔profile ownership): `backend/docs/auth_mvp.md`.

Минимальный воспроизводимый smoke-check для базовой версии: `verification-checklist.md`.
Для reproducible проверки parsing+matching quality: `backend/docs/matching_diagnostics_verification.md`.
Для ручной калибровки score/thresholds: `backend/docs/matching_calibration_note.md`.

## Logging hygiene

- В operational логах сохраняем только технический контекст: `task`, `profile_id`, `vacancy_id`, тайминги, provider/model, counters.
- Не логируем raw-тексты (`resume_text`, `content_text`), `email`, `phone`, raw provider responses и токены.
- Для HH import в логах используется безопасная сводка параметров (например, `text_len`, `extra_params_keys`) вместо полного payload.

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

## Auth MVP

- JWT bearer auth добавлен как минимальный MVP.
- Новые endpoints:
  - `POST /api/v1/auth/register`
  - `POST /api/v1/auth/login`
  - `GET /api/v1/auth/me`
- При регистрации автоматически создаётся `profile` для нового пользователя.
- `profiles` теперь имеют `user_id` и привязаны к `users`.

## Applications funnel MVP

Applications funnel добавляет tracking-слой поверх рекомендаций и docgen:

- текущий pipeline остаётся прежним (matching/docgen не менялись);
- добавлены сущности `applications` и `application_status_history`;
- в `applications` можно хранить текущий статус, short note и привязки к `resume_version_id`/`cover_letter_version_id`.

Поддерживаемые статусы MVP:

- `saved`
- `planned`
- `applied`
- `hr_screen`
- `tech_interview`
- `test_task`
- `offer`
- `rejected`
- `archived`

Новые endpoints:

- `GET /api/v1/profiles/{profile_id}/applications`
- `POST /api/v1/profiles/{profile_id}/applications`
- `GET /api/v1/profiles/{profile_id}/applications/{application_id}`
- `PUT /api/v1/profiles/{profile_id}/applications/{application_id}`
- `POST /api/v1/profiles/{profile_id}/applications/{application_id}/status`
- `GET /api/v1/profiles/{profile_id}/applications/{application_id}/history`
- `DELETE /api/v1/profiles/{profile_id}/applications/{application_id}`

Validation и duplicate policy:

- `vacancy_id` должен существовать;
- application обязательно принадлежит тому же `profile_id`, что и path-параметр;
- `resume_version_id` / `cover_letter_version_id` должны принадлежать этому же профилю;
- их `vacancy_id` должен быть `null` или равен `application.vacancy_id`;
- повторное создание application для пары `(profile_id, vacancy_id)` возвращает `409 Conflict`.

Manual сценарий MVP:

1. Открыть `/vacancies/:vacancyId`.
2. Нажать `Track application` (появится успех + ссылка на `/applications`).
3. Перейти на `/applications` и проверить карточку в колонке статуса.
4. Сменить статус (quick select или в details).
5. Открыть `Edit`, отредактировать note и прикрепить resume/cover letter versions.
6. Проверить `Status history` для application.


## Applications funnel UX polish

`/applications` теперь работает как компактная board-like воронка без drag-and-drop:

- колонки по всем статусам (`saved` → `archived`) показывают count и компактные карточки;
- сверху есть summary-блок: `total`, `active` (без `rejected/archived`), `applied`, `interview stage`, `offers`;
- есть фильтры: `status`, поиск по `vacancy/company`, `hide archived`, сортировка по `updated_at` (по умолчанию newest first);
- на карточке видны title/company/status/updated/note preview + привязанные resume/cover letter (с меткой approved);
- история смены статусов доступна из карточки (`Status history`) и в details-блоке;
- в details можно быстро менять статус кнопками, редактировать note и привязки документов.

Короткий ручной сценарий:

1. Открыть `/vacancies/:vacancyId`.
2. Нажать `Track application`.
3. Перейти на `/applications`: новая карточка появится в `saved`.
4. Через quick status select или details quickbar перевести application между статусами.
5. Открыть `Status history` (на карточке или в details) и проверить события `from → to`.
6. В details прикрепить/проверить resume и cover letter, убедиться что `approved` видно в label.

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

## HH apply from vacancy page (compact MVP UX)

На странице `/vacancies/:vacancyId` добавлен компактный user-facing flow **«Откликнуться через HH»** без bulk apply и без chat orchestration.

Что делает UI:

- показывает prerequisites перед запуском;
- позволяет выбрать `HH managed resume` (из tracked `/integrations/hh-browser/resumes`);
- позволяет опционально выбрать существующую `cover letter version`;
- показывает короткий preview выбранного cover letter;
- запускает `POST /api/v1/integrations/hh-browser/apply`;
- показывает последний apply run по текущей вакансии (`status`, `result`, `finished_at`, safe message);
- после запуска показывает расширенный post-apply summary: связанную локальную application, sync action/reason, HH resume + cover letter, `last apply timestamp`.

### Post-apply synced UX (vacancy page)

После успешного apply пользователь видит не только факт отправки, но и приземлённый результат синхронизации:

- локальный funnel status (обычно `applied`);
- ссылку в `/applications`;
- какой `HH managed resume` использовался;
- какая `cover letter version` использовалась (или что отклик был без письма);
- итоговый safe summary и timestamp последнего external apply.

Для `already_applied` UI показывает **информационное** состояние (без generic red error): HH уже содержит отклик, и отдельно видно, была ли локальная заявка создана/обновлена из этого события.

Для `retryable_failed` и `failed` состояния разведены явно:

- `retryable_failed` — есть понятный путь повторить запуск;
- `failed` — показывается как финальная ошибка без «ложного» сообщения, что funnel уже обновлён;
- если локальный sync не произошёл, это явно указано в summary.

### Prerequisites

Перед нажатием `Откликнуться через HH` ожидается:

1. Активная HH browser session (`connected`, `session_present=true`, `requires_reauth=false`).
2. Существующее HH managed resume (желательно targeted под текущую vacancy).

Если prerequisites не выполнены, UI показывает CTA:

- при неактивной сессии: перейти в `/settings` и переподключить HH;
- при отсутствии managed resume для вакансии: перейти в `/settings` и сначала создать targeted HH resume.

Если у выбранного managed resume visibility = `unknown`, UI показывает предупреждение, но запуск остаётся доступным (backend policy сохраняется).

### Статусы/результаты, которые отображаются в UI

- `submitted` — отклик успешно завершён;
- `failed` — неуспешно, требуется пользовательская проверка условий;
- `retryable_failed` — безопасно повторить после восстановления HH сессии/контекста;
- `already_applied` — calm info state (не показывается как generic error).

### Sync policy: HH apply -> local applications funnel (MVP)

Логика синхронизации теперь явная и локальная (без двустороннего sync с HH кабинетом):

- `submitted`:
  - upsert `applications` по `(profile_id, vacancy_id)`;
  - статус локальной заявки выставляется в `applied`;
  - обновляются связи `last_hh_apply_run_id`, `hh_managed_resume_id`, `cover_letter_version_id`, `external_apply_status=submitted`, `last_external_apply_at`;
  - пишется запись в `application_status_history` c `hh_apply_run_id`.
- `already_applied`:
  - дубликаты `applications` не создаются;
  - локальная заявка синхронизируется в `applied`, но `external_apply_status=already_applied` (предсказуемое отражение результата HH).
- `failed` / `retryable_failed`:
  - локальный статус не переводится в `applied`.

Идемпотентность:

- повторный sync одного и того же `hh_apply_run` не создает дубликаты applications;
- повторный sync не шумит history, так как `application_status_history.hh_apply_run_id` уникален.

### Важно для текущего шага roadmap

- ❗ Это **локальный funnel sync**, а не enterprise CRM/ATS и не full account sync HH.
- ❗ Нет bulk apply UI.
- ❗ Нет post-apply chat actions.

### HH metadata в applications funnel (compact)

В карточках `/applications` для синхронизированных откликов показываются компактные HH-маркеры:

- `HH sync` badge;
- `external apply status` (`submitted` / `already_applied`);
- `HH apply run #...`;
- `HH resume id` и `HH applied at` (если доступно);
- в истории статусов виден `hh_apply_run_id`, чтобы отличать события, пришедшие из HH automation.

### Manual verification checklist (HH apply MVP)

1. Открыть `/vacancies/:vacancyId`.
2. В блоке **Откликнуться через HH** проверить статус HH сессии.
3. Если сессии нет — перейти в `/settings`, подключить HH browser session и вернуться обратно.
4. Выбрать HH managed resume.
5. Опционально выбрать cover letter version и убедиться, что виден краткий preview.
6. Нажать `Откликнуться через HH`.
7. Проверить success/info/error сообщение после выполнения.
8. Проверить блок **Последний HH apply run по вакансии**:
   - `status`,
   - `result`,
   - `updated/finished`,
   - `safe message`,
   - ссылку на HH vacancy (если есть).
9. Подтвердить, что successful/info run (`submitted`/`already_applied`) показывает linked application summary прямо на vacancy page.
10. Перейти в `/applications` и проверить в карточке:
   - `HH sync` badge,
   - внешний apply status,
   - HH run / HH resume / HH applied timestamp.
11. Открыть `Детали` заявки и проверить блок **HH automation linkage** + запись `hh_apply_run_id` в timeline истории.

## HH clusters and extra params

- To preview HH facets (clusters), call `POST /api/v1/import/hh/clusters` with the same body as `/api/v1/import/hh` (`text` is required, plus optional `area`, etc.).
- The response contains `found`, HH `clusters`, and `applied_base_params`.
- Cluster items may include `params` parsed from HH `url`; send them back as `extra_params` in `/api/v1/import/hh` to narrow import results.
- `extra_params` supports values: `string`, `number`, `boolean`, `list[string|number]`, or `null`.

## HH OAuth profile import MVP

Добавлен минимальный OAuth + import flow для профиля пользователя:

- `POST /api/v1/integrations/hh/connect/start` — генерирует HH authorize URL для текущего user.
- `GET /api/v1/integrations/hh/callback` — OAuth callback, сохраняет токены и редиректит в frontend settings.
- `GET /api/v1/integrations/hh/status` — статус подключения (без токенов в ответе).
- `GET /api/v1/integrations/hh/resumes` — список резюме текущего HH аккаунта.
- `POST /api/v1/integrations/hh/import` — явный импорт профиля/резюме (требует `consent=true`).
- `DELETE /api/v1/integrations/hh/connection` — отключение HH интеграции.

Env переменные:

- `HH_OAUTH_CLIENT_ID`
- `HH_OAUTH_CLIENT_SECRET`
- `HH_OAUTH_REDIRECT_URI` (должен совпадать с callback URL в HH приложении)
- `HH_OAUTH_SCOPES` (опционально)
- `HH_OAUTH_STATE_SECRET` (опционально; иначе fallback на `AUTH_JWT_SECRET`)
- `HH_OAUTH_FRONTEND_SUCCESS_URL` (опционально; default `http://localhost:5173/settings?hh=connected`)
- `HH_OAUTH_FRONTEND_ERROR_URL` (опционально; default `http://localhost:5173/settings?hh=connect_failed`)

Импортируемые данные (MVP):

- `profiles`: `full_name`, `title`, `location/city`, `summary_about`, `salary_min`, `remote_ok`, `relocation_ok`, `skills_text`, `resume_text`.
- `profile_experiences` (полный refresh секции).
- `profile_skills` (полный refresh секции).
- `profile_languages` (полный refresh секции).
- `profile_links` (полный refresh секции).

Import policy (MVP):

- main profile поля обновляются из HH payload;
- коллекции `experiences/skills/languages/links` работают в режиме controlled replace-per-section (delete + insert из HH);
- это предотвращает хаотичные дубли и делает поведение предсказуемым.

## HH browser connection foundation UI

В `Settings` добавлен компактный status-блок для foundation слоя HH browser automation:

- показывает backend status из `GET /api/v1/integrations/hh-browser/status`;
- отображает состояния: `disconnected`, `connecting`, `awaiting_code`, `connected`, `requires_reauth`, `failed`;
- показывает безопасные метаданные: `last_authenticated_at`, `session_present`, `last_error_message`;
- базовые действия: `Connect HH` (`POST /connect/init`) и `Disconnect HH` (`POST /disconnect`).

В dev/foundation режиме (например, Vite dev server) дополнительно доступны placeholder-кнопки:

- `Mark awaiting code` (`POST /mark-awaiting-code`)
- `Mark connected` (`POST /mark-connected`)
- `Mark failed` (`POST /mark-failed`)

Это только foundation UX: без real HH login/OTP формы и без embedded browser.  
Ручная проверка переходов состояния:

1. Открыть `/settings` под авторизованным пользователем.
2. В блоке **HH Browser connection (foundation)** нажать `Connect HH` и проверить статус `connecting`.
3. В dev/foundation режиме использовать `Mark awaiting code` → `Mark connected` → `Mark failed`.
4. Нажать `Disconnect HH` и проверить возврат в `disconnected`.



## Targeted HH resume + visibility safety UX (frontend MVP)

В `Settings` реализован компактный safe-flow вокруг targeted HH-резюме:

- точка входа: `/settings` → секция **Targeted HH-резюме (MVP foundation)**;
- перед запуском показывается preview: `target title`, `source profile`, `source resume version`, `skills count`, `experiences count`, vacancy context;
- поддержан dry-run preview (`POST /api/v1/integrations/hh-browser/resumes/create-targeted` с `dry_run=true`);
- action `Создать HH-резюме` запускает реальный create flow;
- после создания есть явный user-facing reminder, что для targeted-резюме безопасно сразу проверить visibility;
- список tracked `HH managed resumes` теперь показывает visibility-блок:
  - `current visibility mode`,
  - `visibility status`,
  - `visibility last checked at`,
  - `visibility last changed at`,
  - `visibility error` (если есть);
- для каждого managed resume доступны компактные действия:
  - `Проверить видимость` (`POST /api/v1/integrations/hh-browser/resumes/{id}/visibility/check`),
  - `Скрыть от всех` (`POST /api/v1/integrations/hh-browser/resumes/{id}/visibility/hide-from-all`),
  - `Обновить статус` (`GET /api/v1/integrations/hh-browser/resumes/{id}/visibility`).

### Почему это безопасный MVP

- По HH-документации новые резюме по умолчанию могут быть видимы работодателям.
- Для точечных/экспериментальных резюме безопасный минимальный путь в продукте — проверить visibility и применить `Скрыть от всех`.
- UX специально ограничен: нет полного privacy-dashboard, нет массовых операций и нет employer-specific matrix в этом шаге.

### Ограничения текущего MVP

- не добавлен employer-specific visibility UI;
- не добавлен share-link UI;
- apply automation из этого UX не включён;
- нет bulk privacy operations/analytics dashboard.

### Manual verification checklist (targeted HH resume + visibility)

1. Открыть `/settings`, в секции **Интеграция HH через браузерную сессию** подключить HH до статуса `connected`.
2. Перейти в секцию **Targeted HH-резюме (MVP foundation)**.
3. Нажать `Создать HH-резюме` и дождаться завершения.
4. Проверить, что после создания показано предупреждение/подсказка о рекомендуемом безопасном шаге `Скрыть от всех`.
5. В таблице tracked managed resumes найти созданное резюме и проверить visibility-поля (`mode/status/last checked/last changed`).
6. Если visibility неизвестна (`unknown`), нажать `Проверить видимость` и убедиться, что статус обновился.
7. Нажать `Скрыть от всех` и проверить success-message + режим `Скрыто от всех`.
8. Принудительно разорвать HH session (disconnect/requires_reauth) и убедиться, что visibility actions не выполняются, а показывается CTA `Переподключить HH`.


### HH fallback JSON import (dev fixtures)

Для разработки/демо без live HH API используйте documented fallback flow:

- canonical fixtures: `backend/tests/fixtures/hh/hh_profile_sample.json`, `backend/tests/fixtures/hh/hh_profile_edge_case.json`
- docs/examples copies: `backend/docs/examples/hh/`
- contract + UI/API guide + verification checklist: `backend/docs/hh_fallback_import_dev_guide.md`

## Saved searches with extra HH filters

- Saved searches now store `filters_json` (JSONB) with additional HH query params (for example, `metro`, `professional_role`).
- New API endpoints under `/api/v1/saved-searches`:
  - `POST /saved-searches`
  - `GET /saved-searches`
  - `PATCH /saved-searches/{id}`
  - `POST /saved-searches/{id}/sync`
  - `GET /saved-searches/{id}/clusters`
- Periodic Celery sync uses `filters_json` from `saved_searches` when requesting HH vacancies.

## Миграции (safe workflow)

Применить миграции:

- `docker compose exec api alembic upgrade head`

Проверить состояние миграций (DB доступность + upgrade до head + `current == heads` + контроль множественных head):

- `docker compose exec api python scripts/verify_migrations.py`

Полезные ручные команды:

- `docker compose exec api alembic current`
- `docker compose exec api alembic heads`
- `docker compose exec api alembic revision --autogenerate -m "add matching tables"`

Если `current` и `heads` не совпадают:

1. Повторите `alembic upgrade head`.
2. Если mismatch остаётся — проверьте историю ревизий и наличие branch/divergence.
3. Если в репозитории случайно несколько head — создайте merge migration (`alembic merge ...`) и зафиксируйте причину в PR.

Когда **не** использовать `alembic stamp head`:

- Когда миграции реально не выполнялись на этой БД.
- Когда причина mismatch не расследована.

`stamp head` только переписывает отметку версии и может скрыть broken schema state.

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


### Frontend auth flow (updated)

- Frontend теперь работает через JWT auth (`/login` и `/register`) и защищённые маршруты.
- После login/register UI делает `GET /api/v1/auth/me`, сохраняет `access_token` и `profile_id` в `localStorage` (`jobsearch_auth_session`).
- Все profile-scoped запросы (`/profiles/{profile_id}/...`) берут `profile_id` из auth session, а не из hardcoded `profile_id=1`.
- Logout очищает auth session и возвращает пользователя на `/login`.
- Demo-flow остаётся рабочим через вход под demo-пользователем (`demo@example.local` / `demo-password-change-me`).

Короткая ручная проверка:

1. Запустить backend + frontend.
2. Открыть `/register`, создать пользователя.
3. Проверить редирект на защищённые страницы (`/vacancies`), затем открыть `/settings`.
4. Обновить профиль и убедиться, что CRUD/рекомендации/детали вакансии/applications работают.
5. Нажать `Logout` и убедиться, что происходит возврат на `/login`.

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
