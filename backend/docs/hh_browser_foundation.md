# HH Browser Connect Orchestration (MVP backend)

Этот PR переводит HH browser integration из foundation-only в **live connect orchestration backend** (MVP), но без UI streaming и без heavy RPA platform.

## Что реализовано

- Явная backend state machine для live connect-flow.
- Отдельный orchestration service (`HHBrowserConnectService`) + runtime registry.
- Browser adapter слой (`PlaywrightHHLoginAdapter`) с детекцией шагов логина HH.
- API для пошагового connect процесса:
  - `POST /api/v1/integrations/hh-browser/connect/start`
  - `GET /api/v1/integrations/hh-browser/connect/state`
  - `POST /api/v1/integrations/hh-browser/connect/identifier`
  - `POST /api/v1/integrations/hh-browser/connect/password`
  - `POST /api/v1/integrations/hh-browser/connect/code`
  - `POST /api/v1/integrations/hh-browser/connect/cancel`

Также сохранены legacy endpoints `/status` и `/disconnect` для обратной совместимости.

## Security guarantees

- **HH password не сохраняется в БД.**
- **OTP code не сохраняется в БД.**
- Credentials/OTP используются только эпизодически внутри live auth step.
- После успешного логина сохраняется только `session_state_ref` (reference), а не raw dump в БД.

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

Нормальный happy-path:

1. `start` -> browser open/login page inspect -> `awaiting_identifier`
2. `identifier` -> `awaiting_password` **или** `awaiting_code`
3. `password` -> `awaiting_code` **или** `connected`
4. `code` -> `connected`

Любой шаг может завершиться в `failed` с normalized error.
`cancel` очищает runtime session и возвращает `disconnected`.

## Login path support in MVP

Реально поддержаны пути:

- `identifier -> next -> password`
- `identifier -> next -> code`
- `identifier -> "Войти с паролем" -> password`

Step detection в adapter строится через live DOM selectors и page state inspection (input/button/url markers), а не через жёсткий static text snippet.

## Session persistence

- Для успешной авторизации browser context storage-state экспортируется адаптером.
- Storage state записывается в файловое dev-safe хранилище (`LocalSessionStorage`).
- В `hh_browser_connections` хранится только `session_state_ref`.

## Safe logging

Логируются только safe operational поля:

- `user_id`
- `connection_id`
- `step/status transition`
- short normalized error code/message
- elapsed timings

Sensitive payloads (identifier/password/otp/cookies/token dump) в логи не пишутся.

## Ограничения MVP

- Нет browser video/streaming и embedded browser UI.
- Нет advanced captcha/anti-bot automation.
- Нет multi-account HH orchestration.
- Playwright должен быть доступен в runtime (иначе сервис отдаёт нормализованную ошибку `PLAYWRIGHT_UNAVAILABLE`).
