# HH Browser Connect Orchestration (hardened step-2 foundation)

Этот PR завершает шаг `connect/login/OTP flow` с акцентом на устойчивость runtime orchestration и безопасную диагностику.

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
