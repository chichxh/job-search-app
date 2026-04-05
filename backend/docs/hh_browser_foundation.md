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

### Restore/check flow

Новые endpoints:

- `POST /api/v1/integrations/hh-browser/session/restore`
- `POST /api/v1/integrations/hh-browser/session/check`

Оба endpoint:

1. Загружают persisted state по `session_state_ref`;
2. Поднимают отдельный browser context из storage_state;
3. Открывают lightweight HH applicant page;
4. Определяют authenticated vs unauthenticated;
5. Возвращают нормализованный `HHBrowserConnectionSummary` (без cookies/tokens).

Политика состояний:

- restore/check success -> `connected`;
- отсутствует `session_state_ref` -> `disconnected` + `SESSION_STATE_MISSING`;
- ref указывает на отсутствующий файл -> `requires_reauth` + `SESSION_STATE_NOT_FOUND`;
- storage state повреждён -> `requires_reauth` + `SESSION_STATE_CORRUPTED`;
- HH показывает logout state -> `requires_reauth` + `SESSION_UNAUTHENTICATED`.

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
