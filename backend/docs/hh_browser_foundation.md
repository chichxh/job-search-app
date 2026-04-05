# HH Browser Integration Foundation (MVP backend)

Этот PR добавляет **только foundation слой** для будущей browser automation интеграции с HH.

## Что есть в этом PR

- Новая таблица `hh_browser_connections` для хранения статуса подключения HH browser-сессии по пользователю.
- API для безопасного управления lifecycle статусов без реальной браузерной автоматизации.
- Safe-поля ошибок (`last_error_code`, `last_error_message`) и session reference (`session_state_ref`) вместо raw browser blob.

## Что в этом PR явно НЕ реализовано

- Нет Playwright/Selenium/browser automation.
- Нет хранения HH login/password.
- Нет хранения или автоматизации SMS/email OTP code.
- Нет orchestration background jobs для automation.
- Нет автоматического apply/create-resume flow.

## Lifecycle статусов

Поддерживаемые статусы:

- `disconnected`
- `connecting`
- `awaiting_code`
- `connected`
- `requires_reauth`
- `failed`

Базовые переходы:

1. `connect/init` → `connecting`
2. `mark-awaiting-code` → `awaiting_code`
3. `mark-connected` → `connected` (очищает ошибки, обновляет `last_authenticated_at`)
4. `mark-failed` → `failed` (записывает короткую safe summary ошибки)
5. `disconnect` → `disconnected` (очищает `session_state_ref` и expiry)

## API foundation endpoints

- `GET /api/v1/integrations/hh-browser/status`
- `POST /api/v1/integrations/hh-browser/connect/init`
- `POST /api/v1/integrations/hh-browser/mark-awaiting-code`
- `POST /api/v1/integrations/hh-browser/mark-connected`
- `POST /api/v1/integrations/hh-browser/mark-failed`
- `POST /api/v1/integrations/hh-browser/disconnect`

Ответы умышленно возвращают только безопасный summary (без raw session/token/page data).
