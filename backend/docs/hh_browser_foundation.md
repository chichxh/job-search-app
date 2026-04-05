# HH Browser Connect Orchestration (hardened step-2 foundation)

Этот PR завершает шаг `connect/login/OTP flow` с акцентом на устойчивость runtime orchestration и безопасную диагностику.

## HH managed resume visibility MVP (backend/domain step-6 foundation)

Добавлен backend/domain foundation для управления видимостью HH managed resume через browser automation contract, **без реализации DOM-автомации модалки в этом PR**.

Почему первым поддержан именно safe path `hidden_from_all`:

- по текущему HH UX новое резюме создается с публичной видимостью (`public_default`);
- после создания targeted resume продуктово-безопасный default для MVP — быстро спрятать резюме от всех;
- расширенная матрица вариантов HH visibility остается следующими шагами (после стабилизации базового сценария).

В локальной tracking-модели `hh_managed_resumes` добавлены поля:

- `desired_visibility_mode`;
- `current_visibility_mode`;
- `visibility_last_checked_at`;
- `visibility_last_changed_at`;
- `visibility_status`;
- `visibility_error_code`;
- `visibility_error_message`.

Поддержанные internal visibility modes в MVP:

- `public_default`;
- `hidden_from_all`;
- `unknown`;
- `change_pending`;
- `change_failed`.

Добавлены backend API контракты:

- `GET /api/v1/integrations/hh-browser/resumes/{id}/visibility`;
- `POST /api/v1/integrations/hh-browser/resumes/{id}/visibility/check`;
- `POST /api/v1/integrations/hh-browser/resumes/{id}/visibility/hide-from-all`.

Оркестрация для check/hide:

1. валидирует ownership резюме;
2. валидирует наличие связанного `hh_resume_external_id`;
3. требует активную HH browser session;
4. вызывает automation contract;
5. сохраняет `current_visibility_mode` + timestamps;
6. при ошибке сохраняет только normalized safe summary (`visibility_error_*`), без raw DOM/cookies/session dumps.

## HH vacancy apply MVP contract (backend/domain step-7 foundation)

Добавлен backend/domain foundation для browser-driven apply flow `one vacancy -> one managed HH resume -> optional cover letter -> submit -> local tracked result`.

Новая tracking-сущность: `hh_apply_runs`.

Локально трекаются поля:

- `user_id`, `profile_id`, `vacancy_id`, `hh_resume_managed_id`;
- `source_cover_letter_version_id` (nullable);
- `status`;
- `hh_vacancy_url`;
- `result_type`, `result_message`;
- `hh_response_ref` (только safe metadata);
- `started_at`, `finished_at`, `created_at`, `updated_at`.

Поддержанные статусы apply-run в MVP:

- `queued`
- `opening_vacancy`
- `awaiting_resume_selection`
- `awaiting_cover_letter`
- `submitting`
- `submitted`
- `failed`
- `retryable_failed`

Добавлены API endpoint'ы:

- `POST /api/v1/integrations/hh-browser/apply`
- `GET /api/v1/integrations/hh-browser/apply-runs`
- `GET /api/v1/integrations/hh-browser/apply-runs/{id}`

Request contract `POST /apply`:

- `vacancy_id` (required)
- `hh_resume_managed_id` (required)
- `cover_letter_version_id` (optional)
- `cover_letter_text` (optional override)
- `dry_run` (optional)
- `force_visibility_check` (optional)

Validation в orchestration:

1. требует активную HH browser session;
2. проверяет ownership managed resume/profile/cover letter;
3. проверяет существование вакансии в локальной DB;
4. проверяет, что managed resume связан с HH (`hh_resume_external_id`);
5. проверяет, что `cover_letter_text` не пустой и ограничен по размеру.

MVP visibility policy:

- если `force_visibility_check=false` — apply flow не блокируется на `unknown`;
- если `force_visibility_check=true`, apply разрешается только для safe modes:
  - `hidden_from_all`
  - `public_default`
  - `unknown`
- если mode явно небезопасный (`change_pending`, `change_failed`) — возвращается normalized `VISIBILITY_CONFIRMATION_REQUIRED`.

Логирование ограничено safe metadata:

- `user_id`, `vacancy_id`, `hh_resume_managed_id`, `apply_run_id`;
- текущий normalized result/status и длительность;
- без полного текста cover letter, без cookies/session dumps, без raw page dumps.

Явно вне scope этого PR:

- фактическая browser submit automation;
- auto-sync в applications funnel;
- bulk/mass apply.

## Create targeted HH resume MVP (backend foundation)

Добавлен backend foundation для создания таргетированного резюме в HH через browser orchestration contract:

- tracking-сущность `hh_managed_resumes` для хранения локального состояния артефактов HH (`draft_local`, `creating`, `created`, `failed`, `stale`);
- endpoint создания:
  - `POST /api/v1/integrations/hh-browser/resumes/create-targeted`;
- endpoint просмотра:
  - `GET /api/v1/integrations/hh-browser/resumes`;
  - `GET /api/v1/integrations/hh-browser/resumes/{id}`;
- deterministic payload builder (без heavy AI rewriting), который собирает:
  - target title/profession,
  - summary,
  - education,
  - skills (+ optional уровни),
  - work experience,
  - targeted emphasis.

В текущем MVP orchestration уже:

1. проверяет активную HH browser session;
2. валидирует ownership profile/source resume/vacancy;
3. создает `hh_managed_resumes` запись;
4. вызывает automation client contract;
5. сохраняет `hh_resume_external_id/url/title` при успехе;
6. сохраняет safe error summary при неуспехе.

Явно **не входит** в текущий scope:

- fill-and-submit всего HH resume constructor wizard;
- visibility control automation;
- vacancy respond/apply automation;
- full reverse-sync резюме из HH в локальную модель.

## Что усилено

- Централизован selector/heuristics layer для HH login page в `PlaywrightHHLoginAdapter`.
- Улучшена детекция шагов логина (identifier/password/code/connected/unknown).
- Добавлены safe retry + timeout policy для transient navigation/wait ошибок.
- Добавлены структурированные transition logs с `connection_id`, `runtime_session_id`, длительностью и reason code.
- В state response добавлен dev-safe debug block:
  - `current_detected_step`
  - `last_transition_at`
  - `runtime_session_alive`

## Поддерживаемые HH login paths

Поддерживаются пути:

1. `identifier -> Дальше -> password -> connected`
2. `identifier -> Дальше -> code -> connected`
3. `identifier -> Войти с паролем -> password -> connected`
4. Already-authenticated state (`/applicant`, `/resume`) -> `connected`

Если текущий экран HH не распознан, flow переводится в `failed` с normalized error `UNRECOGNIZED_STATE` и safe debug summary (без raw DOM/cookies/secrets).

## State lifecycle

Поддерживаемые статусы:

- `disconnected`
- `connecting`
- `awaiting_identifier`
- `awaiting_password`
- `awaiting_code`
- `connected`
- `requires_reauth`
- `failed`

Happy-path:

1. `start` -> open/login inspect -> `awaiting_identifier | awaiting_password | awaiting_code | connected`
2. `identifier` -> `awaiting_password | awaiting_code | connected`
3. `password` -> `awaiting_code | connected`
4. `code` -> `connected`

`cancel` всегда завершает runtime session и возвращает `disconnected`.

## Timeouts, retry, cleanup

- Page navigation timeout контролируется `HH_LOGIN_NAV_TIMEOUT_MS` (по умолчанию 30000 ms).
- Step transition wait timeout контролируется `HH_LOGIN_STEP_TIMEOUT_MS` (по умолчанию 12000 ms).
- Runtime session TTL контролируется runtime registry timeout (по умолчанию 600 сек).
- Retry (один безопасный повтор) применяется для transient ошибок:
  - `TRANSIENT_NAVIGATION`
  - `TRANSIENT_WAIT`
- При abandoned/expired flow runtime закрывается, а connect-state предсказуемо переходит в `failed` + `SESSION_TIMEOUT`.

## Security guarantees

- HH identifier/password/OTP не сохраняются в DB/state response.
- В DB хранится только `session_state_ref` (reference), а не raw browser storage dump.
- Structured logs не содержат секретов (payload values не логируются).
- Unknown/failure debug сводка safe-only (url/title/boolean markers).

## Session persistence and restore/check lifecycle

### Где хранится session state

- После успешного перехода в `connected` сервис экспортирует `Playwright storage_state`.
- Перед сохранением состояние нормализуется до минимально нужного payload:
  - `cookies`
  - `origins` (включая localStorage, если браузер его вернул)
- Payload сохраняется через storage adapter (`LocalSessionStorage`) в файловое хранилище.
- В таблице `hh_browser_connections` хранится только ссылка `session_state_ref` (например `local://hh-browser-session/<file>`).

### Что сохраняется и что НЕ сохраняется

Сохраняется:

- browser cookies;
- browser origins/localStorage из storage_state.

Не сохраняется:

- HH password;
- OTP code;
- raw input payloads connect flow;
- session blob в DB (в БД только reference).

### Validate/restore/check flow

Новые endpoints:

- `POST /api/v1/integrations/hh-browser/session/restore`
- `POST /api/v1/integrations/hh-browser/session/check`
- `POST /api/v1/integrations/hh-browser/session/validate`
- `POST /api/v1/integrations/hh-browser/session/refresh-status`
- `POST /api/v1/integrations/hh-browser/session/require-reauth` (manual override)

Оба endpoint:

1. Загружают persisted state по `session_state_ref`;
2. Поднимают отдельный browser context из storage_state;
3. Открывают lightweight HH applicant page;
4. Определяют authenticated vs unauthenticated;
5. Возвращают нормализованный `HHBrowserConnectionSummary` (без cookies/tokens).

### Явная lifecycle policy (validation outcome -> state transition)

Validation service возвращает нормализованный outcome:

- `valid`
- `expired`
- `logged_out`
- `invalid_storage`
- `network/transient_failure`

Transition policy:

- `valid` -> `connected`, `requires_reauth=false`, обновляет `last_authenticated_at`, очищает `last_error_*`.
- `expired` -> `requires_reauth`, `requires_reauth=true`, `SESSION_EXPIRED`, очищает `session_state_ref`.
- `logged_out` -> `requires_reauth`, `requires_reauth=true`, `SESSION_LOGGED_OUT`, очищает `session_state_ref`.
- `invalid_storage`:
  - `SESSION_STATE_MISSING` -> `disconnected` (сессии нет),
  - `SESSION_STATE_NOT_FOUND` / `SESSION_STATE_CORRUPTED` -> `requires_reauth` + очистка `session_state_ref`.
- `network/transient_failure` -> `failed`, `requires_reauth=false`, session ref не очищается (можно повторить validate позже).

Во всех исходах обновляется `last_checked_at`. `session_expires_at` обновляется только если удаётся безопасно вывести expiry из cookie metadata.

### `requires_reauth` vs `failed`

- `requires_reauth` — пользовательское действие обязательно (HH разлогинил, cookie истекли, или persisted state негоден для восстановления).
- `failed` — техническая/временная проблема в момент проверки (navigation timeout, transient browser/network failure). Пользователь может подождать и повторить validate без немедленного re-login.

### Disconnect cleanup

- `cancel` / `disconnect` физически удаляют persisted session state из storage adapter.
- После cleanup сбрасываются `session_state_ref` и `session_expires_at`.

## Ограничения

- HH DOM может измениться; heuristic detection не гарантирует 100% покрытие всех вариантов UI.
- image captcha / anti-bot challenges полностью не решаются в текущем scope.
- В некоторых сценариях может потребоваться manual reauth/restart flow.

## Troubleshooting

### 1) HH login page изменилась

Симптом: частые `UNRECOGNIZED_STATE` или `HH_SELECTOR_NOT_FOUND`.

Действия:

1. Проверить safe debug поля в `/connect/state` (`current_detected_step`, `runtime_session_alive`).
2. Проверить `HH connect failed` логи с reason code.
3. Обновить centralized heuristics/selectors в `PlaywrightHHLoginAdapter`.

### 2) Flow зациклился в `awaiting_code`

Симптом: после `submit_code` снова возвращается `awaiting_code`.

Действия:

1. Проверить корректность OTP и срок действия кода.
2. Проверить не запрошен ли повторный код HH.
3. Сделать `cancel`, затем `start` и пройти flow заново.

### 3) Session expired

Симптом: `SESSION_TIMEOUT` / runtime не жив.

Действия:

1. Вызвать `POST /connect/start` (при необходимости с `force_restart=true`).
2. Убедиться, что client не держит flow idle дольше runtime TTL.
3. Повторить шаги логина.

### 4) HH logged user out

Симптом: `SESSION_LOGGED_OUT`, статус `requires_reauth`.

Действия:

1. Запустить `connect/start`.
2. Пройти login flow заново.

### 5) Storage invalid

Симптом: `SESSION_STATE_NOT_FOUND` или `SESSION_STATE_CORRUPTED`.

Действия:

1. Считать persisted session непригодной.
2. Переподключить HH через обычный connect flow.

### 6) Temporary validation failure

Симптом: статус `failed` + transient код (например `TRANSIENT_NAVIGATION`).

Действия:

1. Повторить `session/validate` или `session/refresh-status`.
2. Если ошибка стабильная — проверить доступность HH и окружения Playwright.
