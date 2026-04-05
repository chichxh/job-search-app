# Operational runbook (local / docker compose)

Короткий reproducible flow для локального запуска и smoke-проверки.

## 1) Поднять стек

```bash
docker compose -f infra/docker-compose.yml up -d --build
```

Проверить контейнеры:

```bash
docker compose -f infra/docker-compose.yml ps
```

## 2) Применить и проверить миграции

```bash
docker compose -f infra/docker-compose.yml exec api alembic upgrade head
docker compose -f infra/docker-compose.yml exec api python scripts/verify_migrations.py
```

## 3) Проверить health API

```bash
curl -fsS http://127.0.0.1:8000/health
```

Ожидаемо: `{"status":"ok"}`.

## 4) Проверить worker/beat

Проверка, что Celery worker и beat активны:

```bash
docker compose -f infra/docker-compose.yml logs worker --tail=80
docker compose -f infra/docker-compose.yml logs beat --tail=80
```

Ищем события старта задач вида `Task started | task=...` и завершения `Task finished | ...`.

## 5) Demo smoke-path

1. Создать/обновить профиль (`/api/v1/profiles`).
2. Запустить импорт HH (`POST /api/v1/import/hh`).
3. Дождаться completion background task через `GET /api/v1/tasks/{task_id}`.
4. Пересчитать рекомендации (`POST /api/v1/profiles/{profile_id}/recommendations/recompute`).
5. Проверить подборку (`GET /api/v1/profiles/{profile_id}/recommendations`).

## 6) Безопасный просмотр логов

Используйте tail без полного дампа и ориентируйтесь на operational поля:

```bash
docker compose -f infra/docker-compose.yml logs api --tail=150
docker compose -f infra/docker-compose.yml logs worker --tail=150
```

В логах должны быть `profile_id` / `vacancy_id` / `task` / `duration`, но **не** должно быть:
- `resume_text`
- `content_text`
- `email`
- `phone`
- raw provider payload / auth tokens

## 7) Smoke tests / migration checks

```bash
docker compose -f infra/docker-compose.yml exec api pytest -q

docker compose -f infra/docker-compose.yml exec api python scripts/verify_migrations.py
```

## 8) HH automation diagnostics (dev/demo)

Быстрые safe endpoints для operational обзора HH automation:

- `GET /api/v1/integrations/hh-browser/diagnostics`
  - connection snapshot (`status`, `requires_reauth`, `session_present`, `last_checked_at`, `last_authenticated_at`);
  - last action summary;
  - recent failures + compact diagnostic reason;
  - failure distribution by operation code;
  - runtime signal (`playwright_available`).
- `GET /api/v1/integrations/hh-browser/diagnostics/actions?limit=20`
  - последние безопасные action runs по текущему user;
  - без `request_fingerprint`, `context_ref`, storage refs и секретов.

Пример:

```bash
curl -fsS -H "Authorization: Bearer $TOKEN" \
  http://127.0.0.1:8000/api/v1/integrations/hh-browser/diagnostics | jq
```

## 9) HH troubleshooting quick flow

1. Проверить `diagnostics.connection.status` и `requires_reauth`.
2. Посмотреть `recent_failures[0]` (`operation_code`, `diagnostic_reason`, `recommended_next_step`).
3. При необходимости открыть `diagnostics/actions` и посмотреть тренд последних попыток.
4. Сверить с безопасными логами `api` (`hh_*_failed`, `reason=...`, `next_step=...`).

### Частые кейсы

- **HH session expired / requires_reauth**
  - Признак: `status=requires_reauth`, `last_error_code=session_expired|session_logged_out`.
  - Действие: перезапустить connect flow (`/connect/start` → identifier/password/code).

- **Create resume failed**
  - Признак: action `create_targeted_resume` в `retryable_failed`.
  - Если `diagnostic_reason=resume_constructor_surface_unavailable` или `selector_not_found`:
    - проверить HH constructor step вручную;
    - затем inspect page-object/selectors слой.

- **Visibility check/change failed**
  - Признак: `visibility_status=check_failed|change_failed`.
  - Если `diagnostic_reason=visibility_controls_not_found|selector_not_found`:
    - переподключить сессию;
    - если повторяется — проверить селекторы/страницу управления visibility.

- **Apply failed**
  - `diagnostic_reason=already_applied`: retry обычно не нужен, проверить sync в applications.
  - `diagnostic_reason=apply_surface_unavailable`: retry после восстановления HH страницы/сессии.
  - `diagnostic_reason=resume_selection_mismatch`: проверить соответствие managed resume и HH выбора резюме.

- **duplicate/conflict prevented**
  - Признак: `status=duplicate_prevented|conflict_detected|rate_limited`.
  - Действие: не спамить retry, дождаться завершения активного run или использовать сохранённый completed результат.

### Когда retry / reconnect / selectors inspect

- **Retry**: transient/navigation/apply surface проблемы, `retryable_failed`.
- **Reconnect**: `session_expired`, `session_timeout`, `requires_reauth=true`.
- **Inspect selector/page objects**: `selector_not_found`, `page_not_recognized`, повторяемые visibility/constructor/apply UI ошибки.
