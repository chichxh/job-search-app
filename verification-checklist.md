# Base version verification checklist

Этот чек-лист нужен для воспроизводимой ручной проверки “базовой стабильной версии” без расширения фич.

## 0) Prerequisites

- Подготовить `.env` (БД/Redis/LLM/GigaChat и т.д.).
- Запускать команды из корня репозитория.

## 1) Запуск инфраструктуры и backend/frontend

```bash
# поднять сервисы
docker compose -f infra/docker-compose.yml up -d db redis api worker beat frontend

# применить миграции
docker compose -f infra/docker-compose.yml exec api alembic upgrade head
```

## 2) Health-check

```bash
curl -sS http://127.0.0.1:8000/health
```

Ожидаемо: JSON со статусом `ok`.

## 3) Базовые ручные проверки demo-flow (API)

> Ниже использовать реальные `profile_id`, `vacancy_id`, `resume_version_id`, `cover_letter_version_id`.

```bash
# 3.1 список вакансий
curl -sS "http://127.0.0.1:8000/api/v1/vacancies?limit=5&offset=0"

# 3.2 детали вакансии
curl -sS "http://127.0.0.1:8000/api/v1/vacancies/<vacancy_id>"

# 3.3 recommendations recompute
curl -sS -X POST "http://127.0.0.1:8000/api/v1/profiles/<profile_id>/recommendations/recompute?limit=20"

# 3.4 tailoring
curl -sS "http://127.0.0.1:8000/api/v1/profiles/<profile_id>/vacancies/<vacancy_id>/tailoring"

# 3.5 generate resume draft
curl -sS -X POST "http://127.0.0.1:8000/api/v1/profiles/<profile_id>/vacancies/<vacancy_id>/resume/generate"

# 3.6 generate cover letter draft
curl -sS -X POST "http://127.0.0.1:8000/api/v1/profiles/<profile_id>/vacancies/<vacancy_id>/cover-letter/generate"

# 3.7 delete resume version (должен вернуть 204)
curl -i -X DELETE "http://127.0.0.1:8000/api/v1/profiles/<profile_id>/resume-versions/<resume_version_id>"

# 3.8 delete cover letter version (должен вернуть 204)
curl -i -X DELETE "http://127.0.0.1:8000/api/v1/profiles/<profile_id>/cover-letter-versions/<cover_letter_version_id>"
```

## 4) Проверка frontend

```bash
cd frontend
npm install
npm run dev
```

После запуска открыть `http://127.0.0.1:5173` и пройти demo-flow на UI (профиль → вакансии → рекомендации → tailoring → генерация документов).

## 5) Ограничения текущей базовой версии

- LLM provider `openai` не реализован (planned).
- Embedding providers `openai` и `gigachat` не реализованы (planned).
- Чек-лист ориентирован на ручную smoke-проверку; полноценный e2e automation пока не добавлялся в рамках этого этапа.

## 6) Resume file import verification (Settings)

Для полного сценария и ограничений MVP использовать:
- `backend/docs/resume_import_mvp.md`

Короткий path:
1. Login → Settings.
2. Upload `sample_resume.txt` и `sample_resume.pdf` из `backend/tests/fixtures/resume/` (для `.docx` использовать любой локальный текстовый DOCX sample).
3. Verify extracted text (`text length`) не пустой.
4. Verify parsed preview fields (`full_name/title/experiences/skills`).
5. Apply import.
6. Verify профиль обновлён (main fields + experiences + skills).
7. Проверить ограничения:
   - `low_signal_resume.txt` → low-signal/too-short validation error;
   - `no_text_resume.pdf` → no-extractable-text validation error.

## 7) Targeted HH resume + visibility verification (Settings)

1. В `/settings` подключить HH browser session до состояния `connected`.
2. В секции **Targeted HH-резюме (MVP foundation)** убедиться, что action `Создать HH-резюме` активен.
3. Заполнить/проверить поля preview:
   - `target title`;
   - `source profile`;
   - `source internal resume version` (если выбран);
   - `selected/highlighted skills count`;
   - `experiences count`;
   - `vacancy context` (опционально).
4. Нажать `Обновить preview (dry-run)` и проверить сводку preview.
5. Нажать `Создать HH-резюме` и дождаться статуса выполнения.
6. Проверить блок результата:
   - HH resume title;
   - status;
   - external HH URL (если вернулся);
   - created/updated timestamps.
7. Проверить предупреждение после создания: указано, что новое резюме может быть видно и рекомендуется действие `Скрыть от всех`.
8. В таблице локального tracking (`HH managed resumes`) проверить visibility-блок:
   - current mode;
   - visibility status;
   - visibility last checked/changed timestamps;
   - visibility error (если есть).
9. Нажать `Проверить видимость` и убедиться, что visibility status/last checked обновились.
10. Нажать `Скрыть от всех`, проверить success-message и режим `Скрыто от всех`.
11. Для unknown/failed состояния убедиться, что есть понятный retry path (кнопка `Проверить видимость` / `Скрыть от всех` остаётся доступной при активной сессии).
12. Отключить HH browser session и убедиться, что visibility actions блокируются и отображается CTA на reconnect.

Ограничения текущего шага:
- поддержан только safe-path: check visibility + hide-from-all;
- без employer-specific/privacy matrix;
- apply automation пока не включён;
- по умолчанию новый HH resume может быть виден работодателям, поэтому hide-from-all рекомендован сразу после создания targeted-резюме.


## Demo defense flow

1. Запустить docker compose:
   - `docker compose -f infra/docker-compose.yml up -d db redis api worker beat frontend`
2. Применить миграции:
   - `docker compose -f infra/docker-compose.yml exec api alembic upgrade head`
3. Выполнить seed:
   - `docker compose -f infra/docker-compose.yml exec api python scripts/seed_demo_data.py`
4. Открыть frontend (`http://127.0.0.1:5173`).
5. Войти под demo user:
   - email: `demo@example.com`
   - пароль: `demo12345` (или значение `DEMO_USER_PASSWORD` из `.env`).
6. Открыть **Settings**.
7. Нажать **«Авторизоваться через HH»**.
8. Показать блок **«Нет резюме в HH?»**.
9. Открыть **Vacancies**.
10. Открыть **Recommendations**.
11. Открыть карточку вакансии.
12. Показать мэтчинг.
13. Показать сгенерированные документы.
14. Создать отклик.
15. Открыть **Applications**.
16. Показать воронку и историю статусов.
