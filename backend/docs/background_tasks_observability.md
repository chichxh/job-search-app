# Background tasks observability (dev/demo)

Короткая памятка для диагностики Celery pipeline без внешнего monitoring stack.

## 1) Где смотреть логи

- API:
  - `docker compose -f infra/docker-compose.yml logs -f api`
- Worker:
  - `docker compose -f infra/docker-compose.yml logs -f worker`
- Beat (periodic jobs):
  - `docker compose -f infra/docker-compose.yml logs -f beat`

Нормальный паттерн для задач в worker логах:
- `Task started | task=...`
- `Task finished | task=...`
- для ошибок: `Task failed | task=... summary=<ExceptionClass: message>`

## 2) Как проверить состояние задачи

1. Получить `task_id` из enqueue endpoint:
   - `POST /api/v1/import/hh`
   - `POST /api/v1/dev/vacancies/hh/backfill-parsed`
   - `POST /api/v1/profiles/{profile_id}/recommendations/recompute`
   - `POST /api/v1/saved-searches/{id}/sync`
2. Проверить состояние:
   - `GET /api/v1/tasks/{task_id}`

В ответе теперь полезны поля:
- `state` (`PENDING` | `STARTED` | `SUCCESS` | `FAILURE`)
- `task_name`
- `started_at`, `finished_at`
- `message`
- `error_summary` (краткая причина при `FAILURE`)

## 3) Как понять, что задача зависла/упала

- **Упала**: `state=FAILURE`, есть `error_summary`, в worker-логах есть `Task failed ... summary=...`.
- **Похоже зависла**: долго держится `state=STARTED`, нет `Task finished` в логах, и `started_at` заметно в прошлом относительно ожидаемой длительности для конкретного flow.

## 4) Что считать нормой

- Для длинных задач (HH import, parsing backfill, embeddings rebuild, recommendations recompute) должен появляться `STARTED` со смысловым `message`.
- После завершения в `SUCCESS`-result возвращается `_task.duration_ms` и timestamps.
- Для beat-пайплайна Saved Searches в логах виден запуск `schedule_saved_search_sync` и число enqueued sync задач.
