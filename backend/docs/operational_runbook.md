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
