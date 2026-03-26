# Testing

## Smoke / integration suite (backend)

Этот PR добавляет минимальный backend smoke suite для demo-flow API.

### Что входит в smoke suite

Файл: `backend/tests/test_api_smoke_flow.py`

Покрываются сценарии:
- health check (`/health`)
- profile read/write path (create + update)
- recommendations endpoint (структура ответа)
- tailoring endpoint (explanation + evidence)
- docgen draft creation (happy path)
- approve resume version
- approve cover letter version
- docgen failure-path с нормализованной ошибкой

### Как запускать

Из корня репозитория:

```bash
cd backend
python -m pytest tests/test_api_smoke_flow.py
```

Или весь backend tests пакет:

```bash
cd backend
python -m pytest tests
```

### Что замокано

Чтобы тесты были устойчивыми и не зависели от внешних сервисов:
- отключены реальные вызовы Celery task enqueue для profile embeddings
- замокан docgen service layer (LLM/provider не вызывается)
- используется in-memory fake DB session для API dependency override
- отсутствуют реальные запросы в HH/import и в LLM providers

Это intentional: suite проверяет интеграцию API-слоя и контрактов ответов, но не ходит в интернет/внешние провайдеры.


## Migration safety check

Лёгкий smoke-check миграций на живой БД (локально/в CI):

```bash
cd backend
python scripts/verify_migrations.py
```

Проверка фейлится, если БД недоступна, миграции не применяются до `head`, `current != heads` или появились неожиданные множественные `heads`.
