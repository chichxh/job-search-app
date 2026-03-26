# Модель данных и база данных (PostgreSQL + pgvector)

**Статус:** **[NOW]** актуальная структура БД включает нормализованные профили, пайплайн вакансий с `vacancy_parsed`, мэтчинг и версии документов. **[NEXT]** — метаданные генерации через LLM и новые сущности “воронки откликов”.

Документ описывает логическую модель данных, ключевые таблицы, связи, важные индексы и рекомендации по миграциям/обслуживанию.

---

## 1) Обзор: основные сущности и связи

Система хранит данные в PostgreSQL. Для семантического поиска используется расширение **pgvector** и HNSW индексы.

Ключевые сущности:

- **Профиль соискателя**: `profiles` + набор таблиц `profile_*`
- **Вакансии**: `vacancies` + нормализация текста `vacancy_parsed` + требования `vacancy_requirements`
- **Эмбеддинги**: `profile_embeddings_v2`, `vacancy_embeddings_v2`
- **Мэтчинг**: `vacancy_scores` + доказательства `resume_evidence`
- **Документы**: `resume_versions`, `cover_letter_versions`
- **Поисковые запросы пользователя**: `saved_searches`

### 1.1 Связи (кардинальности)

- `profiles (1) → (N) profile_experiences / profile_projects / profile_achievements / ...`
- `profiles (1) → (N) resume_versions`, `profiles (1) → (N) cover_letter_versions`
- `profiles (1) → (N) profile_embeddings_v2` _(по факту 1 запись на профиль в v2, но это зависит от реализации)_
- `vacancies (1) → (1) vacancy_parsed`
- `vacancies (1) → (N) vacancy_requirements`
- `vacancies (1) → (N) vacancy_embeddings_v2` _(по факту 1 на вакансию)_
- `profiles (N) ↔ (N) vacancies` через `vacancy_scores` (по паре profile_id/vacancy_id)
- `resume_evidence` привязана к конкретной паре (profile_id, vacancy_id) и используется в explainability

---

## 2) Таблицы профиля

### 2.1 `profiles` — карточка соискателя

Назначение: хранит идентификацию, контакты, предпочтения и “настройки” пользователя.

**Основные поля (фактические по твоей схеме):**

- Идентификация/контакты: `full_name`, `email`, `phone`, `telegram`
- Локация: `location`, `city`, `country`, `metro`
- Легальные: `citizenship`, `work_authorization_country`, `needs_sponsorship`
- Доступность: `available_from`, `notice_period_days`
- Формат работы: `preferred_employment`, `preferred_schedule`, `remote_ok`, `relocation_ok`
- Финансы: `salary_min`
- Предпочтения: `preferred_industries` (jsonb), `preferred_company_types` (jsonb), `interest_tags` (jsonb), `preferred_tech` (jsonb), `excluded_tech` (jsonb), `team_preferences_json` (jsonb)
- Проф. сводка: `summary_about`, `seniority_level`, `years_total`
- Legacy поля: `title`, `resume_text`, `skills_text`
- Системные: `created_at`, `updated_at`

> Рекомендация: со временем legacy поля можно оставить только как fallback, а “истиной” считать `resume_versions` + `profile_skills`.

---

### 2.2 `profile_experiences` — опыт работы

Назначение: хранит трудовой опыт и тексты обязанностей/достижений для ATS/evidence и генерации документов.

Поля:

- FK: `profile_id`
- `company_name`, `position_title`, `location`
- `start_date`, `end_date`, `is_current`
- `responsibilities_text`, `achievements_text`, `tech_stack_text`
- `employment_type`
- `created_at`

---

### 2.3 `profile_projects` — проекты

Назначение: проекты часто используются в сопроводительных письмах и tailoring, поэтому выделены отдельно.

Поля:

- FK: `profile_id`
- `name`, `role`, `description_text`
- `start_date`, `end_date`
- `tech_stack_text`, `url`
- `created_at`

---

### 2.4 `profile_achievements` — достижения с метриками

Назначение: единый список достижений, которые можно “вытаскивать” в резюме и письма.

Поля:

- FK: `profile_id`
- `title`, `description_text`, `metric`, `achieved_at`
- ссылки: `related_experience_id`, `related_project_id` (nullable)
- `created_at`

---

### 2.5 `profile_education` — образование

Поля:

- FK: `profile_id`
- `institution`, `degree_level`, `field_of_study`
- `start_year`, `end_year`
- `description_text`, `gpa`
- `created_at`

---

### 2.6 `profile_certificates` — сертификаты

Поля:

- FK: `profile_id`
- `name`, `issuer`, `issued_at`, `expires_at`, `url`
- `created_at`

---

### 2.7 `profile_skills` — навыки (включая уровень и доказательства)

Назначение: ключевой источник для “ATS-проходимости” и объяснимости.

Поля:

- FK: `profile_id`
- `name_raw`, `normalized_key`
- `category` (technical/soft/...)
- `level` (beginner/intermediate/advanced/expert/unspecified)
- `years`, `last_used_year`
- `is_primary`
- `evidence_text` (особенно для soft skills)
- `created_at`

> Индекс на `normalized_key` повышает скорость мэтчинга.

---

### 2.8 `profile_languages` — языки

Поля: `profile_id`, `language`, `level`, `created_at`

---

### 2.9 `profile_links` — ссылки

Поля: `profile_id`, `type`, `url`, `label`, `created_at`  
(используется для портфолио/соцсетей/ссылок на компании/ссылки резюме)

---

## 3) Таблицы вакансий

### 3.1 `vacancies` — основной слой вакансий

Назначение: хранит исходные вакансии (включая HTML-описание) и метаданные.

Поля (типовые):

- `id`, `source`, `external_id`
- `title`, `company_name`, `location`
- `salary_from`, `salary_to`, `currency`
- `description` (для HH часто HTML)
- `url`, `status`
- `created_at`, `updated_at`

---

### 3.2 `vacancy_parsed` — нормализованный слой вакансии (ключевое решение)

Назначение: решает проблему “плоских данных” и HTML-шума.

Поля:

- `vacancy_id` (PK и FK на `vacancies.id`, CASCADE)
- `plain_text` — очищенный текст
- `sections_json` — JSON с секциями:
    - `responsibilities`, `requirements`, `nice_to_have`, `conditions`, `other`
    - каждая секция хранит `lines` и `text`
- `extracted_at`
- `version` — версия парсера (например `hh_sections_v1`)
- `quality_score` (0..1) — качество извлечения секций

Используется:

- для embeddings (семантика)
- для извлечения требований must/nice
- для эвристик eligibility (например, релокация)

---

### 3.3 `vacancy_requirements` — требования вакансии

Назначение: единый формат требований для ATS и скрининга.

Поля (типовые по текущей логике):

- FK: `vacancy_id`
- `kind`: `skill` | `constraint`
- `raw_text` (как встретилось)
- `normalized_key`
- `is_hard` (must-have)
- `weight` (например, must=3, nice=1)
- (опционально) `source` / `extraction_version` — если добавите позже

---

## 4) Эмбеддинги (v2)

### 4.1 `vacancy_embeddings_v2`

Назначение: хранит вектор вакансии для семантического поиска.

Поля:

- `id`, `vacancy_id`
- `embedding` (vector(dim))
- (опционально) `model_name`, `created_at`

Индекс:

- HNSW по `embedding` для ускорения поиска top-N

---

### 4.2 `profile_embeddings_v2`

Назначение: хранит вектор профиля для поиска релевантных вакансий.

Поля:

- `id`, `profile_id`
- `embedding` (vector(dim))
- (опционально) `model_name`, `created_at`

---

## 5) Мэтчинг и explainability

### 5.1 `vacancy_scores`

Назначение: хранит результат мэтчинга для пары (profile, vacancy).

Поля:

- `profile_id`, `vacancy_id`
- `final_score`, `verdict` (strong/ok/weak/reject)
- `explanation` (JSONB)
- `created_at`/`updated_at` (если есть)

**explanation** содержит:

- eligibility: ok/reasons_failed/warnings
- ats: keywords_present/missing/uncertain/keywords_to_add + suggestions
- semantic: score
- final: score + components breakdown

---

### 5.2 `resume_evidence`

Назначение: хранит подтверждения (фрагменты профиля/резюме), которыми объясняется match.

Поля:

- `profile_id`, `vacancy_id`
- `evidence_text`
- `confidence`
- `evidence_type` (например `skill_match`)
- `created_at`

---

## 6) Документы (версии резюме и писем)

### 6.1 `resume_versions`

Назначение: хранит несколько версий резюме (общие и заточенные под вакансию).

Поля:

- `profile_id`
- `vacancy_id` (nullable)
- `title`
- `content_text`
- `format` (plain/markdown)
- `source` (user/ai/legacy_import)
- `status` (draft/approved/archived)
- `created_at`, `approved_at`

---

### 6.2 `cover_letter_versions`

Назначение: хранит версии сопроводительных писем.

Поля:

- `profile_id`
- `vacancy_id` (nullable)
- `title`
- `subject`
- `content_text`
- `source`, `status`
- `created_at`, `approved_at`

---

## 7) Saved searches

### `saved_searches`

Назначение: хранит пользовательские поисковые запросы и фильтры для регулярной синхронизации вакансий.

Типовые поля:

- `text`, параметры фильтров (json), `is_active`, `created_at`/`updated_at`
- используется Celery beat для регулярного импорта

---

## 8) Индексы и ограничения (рекомендации)

### 8.1 Внешние ключи

- `profile_*` таблицы: FK на `profiles.id` с `ON DELETE CASCADE`
- `vacancy_parsed`: FK на `vacancies.id` с `ON DELETE CASCADE`
- `resume_versions`/`cover_letter_versions`: FK на `profiles.id` (`CASCADE`), FK на `vacancies.id` (`SET NULL`)

### 8.2 Уникальности

- `vacancy_scores`: уникальность пары `(profile_id, vacancy_id)` (upsert-логика)
- `vacancy_parsed`: `vacancy_id` как PK (1:1)
- embeddings: желательно уникальность по `vacancy_id` и `profile_id` (если 1 запись на сущность)

### 8.3 Индексы

- `profile_skills.normalized_key`
- `vacancy_requirements.vacancy_id` + `(vacancy_id, kind)`
- `vacancy_parsed.extracted_at`, `vacancy_parsed.version` (для backfill)
- HNSW индексы для `*_embeddings_v2.embedding`

---

## 9) Миграции Alembic: рекомендации

### 9.1 Правила

- Каждое изменение схемы — отдельная миграция.
- При добавлении JSONB:
    - задавать `server_default` (`'{}'` или `'[]'`) чтобы избежать NULL и упростить код.
- При изменении embedding dim:
    - создавать новую таблицу `*_embeddings_v2`, а не менять старую “на месте” (как вы уже сделали).

### 9.2 Проверка состояния миграций

- `alembic current` должен совпадать с `alembic heads`
- при деплое: миграции применяются до старта worker/beat

---

## 10) Data backfill / фиксация качества данных

Система предусматривает механизмы “починки” данных:

- Backfill парсинга вакансий (`vacancy_parsed`) при улучшении логики извлечения
- Пересчёт requirements (must/nice)
- Пересчёт embeddings v2
- Пересчёт vacancy_scores для профилей

---

## 11) Будущие расширения модели данных

- **[NEXT]** LLM meta:
    - хранить `provider`, `model`, `prompt_version`, `input_hash` для каждой версии документа
- **[FUTURE]** Applications tracking:
    - `applications` (profile_id, vacancy_id, status, created_at)
    - `application_status_history` (status, note, timestamp)
- **[FUTURE]** Multi-user:
    - `users` + ownership связка users↔profiles
- **[FUTURE]** OSINT:
    - таблицы внешних источников и оценка достоверности


# API документация (Backend /api/v1)

**Статус:** **[NOW]** профили (включая нормализованные таблицы), вакансии, импорт HH, мэтчинг, версии документов и задачи доступны через API. **[NEXT]** добавление LLM-генерации (GigaChat) через отдельные эндпоинты/таски.

Эта документация описывает основные группы эндпоинтов, ожидаемые входные/выходные данные и примеры запросов.

> Актуальная спецификация всегда доступна в Swagger/OpenAPI:  
> `http://localhost:8000/docs`

---

## 1) Общая информация

- **Base URL:** `http://localhost:8000/api/v1`
- **Формат:** JSON
- **Авторизация:** JWT Bearer Auth MVP (`/auth/register`, `/auth/login`, `/auth/me`), с ownership связью `users -> profiles`.

### 1.1 Ошибки

- `400` — некорректный запрос
- `404` — ресурс не найден
- `422` — ошибка валидации (pydantic)
- `429` — rate limit (внешние API/LLM)
- `500` — ошибка сервера/интеграции

---

## 2) Profiles (профили и настройки)

### 2.1 CRUD профилей

- `GET /profiles` — список профилей
- `GET /profiles/{profile_id}` — получить профиль
- `POST /profiles` — создать профиль
- `PUT /profiles/{profile_id}` — обновить профиль

**Поля профиля** включают: контакты, локацию, предпочтения/интересы, легальные поля, доступность, summary, а также legacy `resume_text`/`skills_text`.

**Пример: создать профиль**

curl -X POST "http://localhost:8000/api/v1/profiles" \  
  -H "Content-Type: application/json" \  
  -d '{  
    "title":"Senior Backend Developer (Python)",  
    "full_name":"Иван Иванов",  
    "city":"Москва",  
    "country":"Russia",  
    "remote_ok": true,  
    "relocation_ok": false,  
    "summary_about":"Senior backend developer...",  
    "skills_text":"Python; FastAPI; PostgreSQL"  
  }'

---

## 3) Нормализованные данные профиля (profile_*)

Каждый блок хранится в отдельной таблице и управляется отдельными эндпоинтами.  
**Паттерн:**

- `GET /profiles/{profile_id}/{entity}` — список
- `POST /profiles/{profile_id}/{entity}` — создать
- `PUT /profiles/{profile_id}/{entity}/{id}` — обновить
- `DELETE /profiles/{profile_id}/{entity}/{id}` — удалить

### 3.1 Опыт работы

- `/profiles/{profile_id}/experiences`

**Пример: добавить опыт**

curl -X POST "http://localhost:8000/api/v1/profiles/1/experiences" \  
  -H "Content-Type: application/json" \  
  -d '{  
    "company_name":"Cordless",  
    "position_title":"Senior Backend Developer",  
    "start_date":"2022-07-01",  
    "end_date":"2023-11-01",  
    "is_current":false,  
    "responsibilities_text":"Разработка сервисов...",  
    "achievements_text":"Event-driven архитектура...",  
    "tech_stack_text":"Python; Kafka; Docker"  
  }'

### 3.2 Проекты

- `/profiles/{profile_id}/projects`

### 3.3 Достижения

- `/profiles/{profile_id}/achievements`

### 3.4 Образование

- `/profiles/{profile_id}/education`

### 3.5 Сертификаты

- `/profiles/{profile_id}/certificates`

### 3.6 Навыки

- `/profiles/{profile_id}/skills`

### 3.7 Языки

- `/profiles/{profile_id}/languages`

### 3.8 Ссылки

- `/profiles/{profile_id}/links`

---

## 4) Вакансии (Vacancies)

### 4.1 Просмотр вакансий

- `GET /vacancies` — список вакансий
- `GET /vacancies/{vacancy_id}` — детали вакансии
- `POST /vacancies` — создать вакансию вручную (manual)

**Пример: создать manual вакансию**

curl -X POST "http://localhost:8000/api/v1/vacancies" \  
  -H "Content-Type: application/json" \  
  -d '{  
    "source":"manual",  
    "external_id":"m-001",  
    "title":"Senior Python Backend Developer",  
    "company_name":"ExampleTech",  
    "location":"Remote",  
    "description":"Python, FastAPI, PostgreSQL, Redis. Kafka/RabbitMQ...",  
    "status":"open",  
    "url":"https://example.com/vacancy/m-001"  
  }'

---

## 5) Импорт вакансий из HeadHunter (HH)

### 5.1 Импорт вакансий (асинхронно)

- `POST /import/hh` — запускает импорт вакансий по поисковому запросу
- `POST /import/hh/clusters` — (если используется) получает кластеры

**Пример запуска импорта**

curl -X POST "http://localhost:8000/api/v1/import/hh" \  
  -H "Content-Type: application/json" \  
  -d '{  
    "text":"python developer",  
    "area":2,  
    "per_page":20,  
    "pages_limit":2,  
    "fetch_details":true,  
    "extra_params":{}  
  }'

Ответ:

{"task_id":"<celery_task_id>"}

### 5.2 Backfill парсинга вакансий (dev) — **[NOW] если добавлен**

- `POST /dev/vacancies/hh/backfill-parsed?limit=...&only_missing=true`

Используется для перепарсинга `vacancy_parsed` и пересоздания requirements после изменения логики парсинга.

---

## 6) Parsing и требования вакансии (внутренний слой данных)

### 6.1 vacancy_parsed

**Прямые CRUD эндпоинты могут отсутствовать** (обычно это служебная таблица).  
Проверять можно через SQL или через детали вакансии (если API отдаёт `parsed`).

Содержимое:

- `plain_text`
- `sections_json` (responsibilities/requirements/nice_to_have/conditions/other)
- `quality_score`, `version`, `extracted_at`

### 6.2 vacancy_requirements

Аналогично — чаще используется внутренне.  
Содержит:

- `kind=skill|constraint`
- `is_hard` + `weight` для must/nice

---

## 7) Embeddings (v2) — dev endpoints

Чаще всего embeddings пересчитываются автоматически после импорта, но для диагностики полезны dev-эндпоинты.

Примеры (варианты зависят от проекта):

- `POST /dev/embeddings/rebuild-vacancies?limit=10`
- `POST /dev/embeddings/rebuild-profiles?profile_id=1`

> Если у вас эти роуты называются иначе — смотри `/docs`.

---

## 8) Matching / Recommendations (мэтчинг)

### 8.1 Получить рекомендации

- `GET /profiles/{profile_id}/recommendations?limit=50`

Возвращает список вакансий с `final_score` и `verdict`.

### 8.2 Запустить пересчёт рекомендаций

- `POST /profiles/{profile_id}/recommendations/recompute?limit=50`

Возвращает `task_id`.

### 8.3 Tailoring по конкретной вакансии

- `GET /profiles/{profile_id}/vacancies/{vacancy_id}/tailoring`

Возвращает:

- `explanation` (eligibility/ats/semantic/final)
- `evidence` (resume_evidence)

**Пример**

curl "http://localhost:8000/api/v1/profiles/1/vacancies/10/tailoring"

---

## 9) Версии документов (резюме и письма)

### 9.1 Резюме

- `GET /profiles/{profile_id}/resume-versions`
- `POST /profiles/{profile_id}/resume-versions`
- `PUT /profiles/{profile_id}/resume-versions/{id}`
- `POST /profiles/{profile_id}/resume-versions/{id}/approve`

### 9.2 Сопроводительные

- `GET /profiles/{profile_id}/cover-letter-versions`
- `POST /profiles/{profile_id}/cover-letter-versions`
- `PUT /profiles/{profile_id}/cover-letter-versions/{id}`
- `POST /profiles/{profile_id}/cover-letter-versions/{id}/approve`

---

## 10) Генерация документов через LLM — **[NEXT]**

Планируемые эндпоинты (после подключения GigaChat):

- `POST /profiles/{profile_id}/vacancies/{vacancy_id}/resume/generate`
- `POST /profiles/{profile_id}/vacancies/{vacancy_id}/cover-letter/generate`

Они будут:

- собирать факты профиля + tailoring
- создавать `draft` версию документа
- возвращать `resume_version_id` / `cover_letter_version_id` или `task_id` (если генерация через Celery)

---

## 11) Saved searches

- `GET /saved-searches`
- `POST /saved-searches`
- `POST /saved-searches/{id}/sync` — ручной запуск синхронизации
- (beat) периодическая синхронизация активных поисков

---

## 12) Tasks (статус фоновых задач)

- `GET /tasks/{task_id}` — статус задачи Celery

Используется для:

- импорт HH
- backfill parsing
- rebuild embeddings
- recompute recommendations
- **[NEXT]** генерации документов LLM

---

## 13) Рекомендованный сценарий проверки API (коротко)

1. Создать/обновить профиль + skills/experience
2. Импортировать вакансии HH
3. Backfill parsing (если меняли парсер)
4. Пересчитать embeddings
5. Пересчитать рекомендации
6. Взять top вакансии → открыть tailoring → проверить evidence


# Модуль мэтчинга (Matching) и объяснимость рекомендаций

**Статус:** **[NOW]** модуль мэтчинга работает на гибридном подходе (hard filters + ATS-покрытие требований + семантическая близость через embeddings v2) и формирует объяснения (`explanation`) и доказательства (`resume_evidence`). **[NEXT]** — подключение LLM для генерации резюме/письма на основе `tailoring` без галлюцинаций.

Документ описывает входные данные, алгоритм, формулу скоринга, структуру объяснений, хранение результатов и проверки качества.

---

## 1) Назначение и принципы

Модуль мэтчинга реализует подход **“перевёрнутого ATS”**: система оценивает не “похожесть”, а вероятность того, что кандидат пройдёт автоматизированные и формальные этапы отбора.

Основные принципы:

1. **Отсечки (eligibility)**: если вакансия заведомо не подходит по формальным условиям, она получает `reject` независимо от похожести текста.
2. **ATS-покрытие требований**: must-have (hard) требования важнее nice-to-have.
3. **Семантика дополняет правила**: embeddings помогают находить смысловую релевантность даже при разных формулировках.
4. **Объяснимость**: результат всегда сопровождается структурированным `explanation` и `resume_evidence`.

---

## 2) Входные данные мэтчинга

Мэтчинг работает на паре объектов: **профиль соискателя** и **вакансия**.

### 2.1 Профиль (profile)

Используются данные из:

- `profiles` (summary_about, city, remote_ok, relocation_ok, salary_min, доступность)
- `profile_skills` (name_raw, normalized_key, level, years, is_primary, evidence_text)
- `profile_experiences` (responsibilities_text, achievements_text, tech_stack_text)
- `profile_projects` и `profile_achievements`
- `resume_versions` (предпочтительно approved версия) / fallback на `profiles.resume_text`

Также используется эмбеддинг профиля:

- `profile_embeddings_v2`

### 2.2 Вакансия (vacancy)

Используются данные из:

- `vacancies` (title, company, location, salary, статус)
- `vacancy_parsed`:
    - `plain_text`
    - `sections_json` (responsibilities/requirements/nice_to_have/conditions/other)
    - `quality_score`
- `vacancy_requirements`:
    - `kind=skill` и `kind=constraint`
    - `is_hard` и `weight`

Также используется эмбеддинг вакансии:

- `vacancy_embeddings_v2`

---

## 3) Общая схема алгоритма

Для пары (profile_id, vacancy_id) вычисляются:

1. **Eligibility**: проходит ли кандидат формальные условия
2. **ATS score**: насколько кандидат покрывает hard/nice требования вакансии
3. **Semantic score**: смысловая близость профиля и вакансии
4. **Final score**: итоговая оценка и verdict
5. **Explainability**: формирование `explanation` и `resume_evidence`

---

## 4) Этап 1: Eligibility (формальные отсечки)

Цель — смоделировать фильтры, которые часто приводят к автоматическому отказу на ранних этапах.

Типовые правила:

- **Relocation requirement**: если вакансия требует релокацию, а профиль `relocation_ok=false` → reject
- **Remote/Office**: если вакансия офисная, а кандидат рассматривает только удалёнку (или наоборот) → reject/penalty
- **Location mismatch**: если вакансия привязана к городу, а кандидат не готов к переезду/офису → reject
- **Salary constraints**: если у кандидата `salary_min`, а в вакансии верхняя граница ниже → reject или warning (в зависимости от политики)
- **Experience constraints**: если вакансия требует 3–6 или 6+ лет, а у профиля явно меньше → reject или сильный штраф

Результат этапа:

"eligibility": {  
  "ok": true|false,  
  "reasons_failed": ["..."],  
  "warnings": ["..."]  
}

---

## 5) Этап 2: ATS слой (покрытие требований must/nice)

ATS слой основан на таблице `vacancy_requirements`.

### 5.1 Требования вакансии

- **Hard (must-have)**: `is_hard=true`, `weight=3`
- **Nice-to-have**: `is_hard=false`, `weight=1`

Требования извлекаются из:

- `vacancy_parsed.sections_json.requirements` → hard
- `vacancy_parsed.sections_json.nice_to_have` → nice
- fallback: по маркерам в строках и по всему plain_text

### 5.2 Сопоставление с профилем

Мэтчинг навыков выполняется в приоритетном порядке:

1. **Нормализованные навыки профиля**
    - `profile_skills.normalized_key` сравнивается с `vacancy_requirements.normalized_key`
    - учитываются алиасы и токены (без substring-ошибок типа Git vs GitHub)
2. **Сопоставление по токенам в текстах профиля**
    - используется, если навык не найден в таблице skills
    - тексты: summary + experiences + projects + резюме
3. **Уровень навыка (skill level)**
    - если навык найден, но `level=beginner`, а требование hard → попадает в `uncertain`, а не `present`

### 5.3 Метрики ATS

- `hard_coverage = found_hard_weight / total_hard_weight`
- `nice_coverage = found_nice_weight / total_nice_weight`

> Важно: если `total_hard_weight=0`, это не означает идеальное совпадение.  
> Политика качества:
> 
> - если у вакансии нет skill требований или `quality_score` низкий → добавлять warning и ограничивать максимум verdict.

### 5.4 Выход ATS в explanation

"ats": {  
  "keywords_present": ["Python","PostgreSQL"],  
  "keywords_missing_must": ["Kafka"],  
  "keywords_missing_nice": ["Kubernetes"],  
  "keywords_uncertain": ["Django REST Framework"],  
  "keywords_to_add": ["Kafka","DRF"],  
  "structure_suggestions": ["..."]  
}

---

## 6) Этап 3: Semantic score (embeddings v2)

Используется семантическая близость между эмбеддингами профиля и вакансии:

- embedding(profile) ∈ `profile_embeddings_v2`
- embedding(vacancy) ∈ `vacancy_embeddings_v2`

Метрика:

- cosine similarity через pgvector (или преобразование из cosine distance)

Назначение semantic score:

- помогает ранжировать вакансии, даже если текст сформулирован иначе;
- формирует candidate set (top-N) для подробного мэтчинга.

---

## 7) Итоговый скоринг и вердикт

### 7.1 Формула

Используется комбинированная формула, например:

`final = 0.45 * semantic + 0.35 * hard_coverage + 0.20 * nice_coverage`

Дополнительно могут применяться penalties/warnings:

- overqualified
- salary mismatch warnings
- low parsing quality

### 7.2 Вердикты

- `reject`: eligibility.ok=false или финальный балл ниже порога
- `weak`: низкая релевантность / пробелы в must-have
- `ok`: достаточное соответствие
- `strong`: высокая вероятность прохождения

Пороговые значения устанавливаются конфигом и могут калиброваться на размеченных данных.

### 7.3 Ранжирование

Для UX важно, чтобы `reject` не попадали в топ:

- либо `final_score=0` при `eligibility.ok=false`
- либо отдельное поле `rank_score`

---

## 8) Explainability: evidence и структура explanation

### 8.1 resume_evidence

Для каждого обнаруженного соответствия система пытается найти подтверждение в:

1. experiences / projects / achievements
2. resume_version (approved)
3. legacy resume_text

Каждый evidence элемент содержит:

- `evidence_text` (фрагмент текста)
- `confidence` (1.0 exact, 0.8 alias/partial)
- `evidence_type` (например `skill_match`)

### 8.2 explanation JSON (пример)

{  
  "eligibility": {"ok": true, "reasons_failed": [], "warnings": []},  
  "ats": {  
    "keywords_present": ["Python","PostgreSQL"],  
    "keywords_missing_must": ["Kafka"],  
    "keywords_missing_nice": ["Kubernetes"],  
    "keywords_uncertain": [],  
    "keywords_to_add": ["Kafka"],  
    "structure_suggestions": ["Добавьте достижения с метриками."]  
  },  
  "semantic": {"score": 0.62},  
  "final": {  
    "score": 0.71,  
    "verdict": "ok",  
    "components": {"semantic": 0.62, "hard": 0.66, "nice": 0.50},  
    "penalties": []  
  },  
  "warnings": ["low_quality_vacancy_parsing"]  
}

---

## 9) Хранение результатов

- `vacancy_scores`: результат мэтчинга по паре `(profile_id, vacancy_id)`
- `resume_evidence`: доказательства по той же паре

Мэтчинг идемпотентен: при пересчёте пара обновляется (UPSERT), evidence пересоздаётся.

---

## 10) Качество и диагностика

### 10.1 Типичные причины плохих рекомендаций

- низкий `quality_score` у вакансии → мало требований → hard слой слабый
- ошибки нормализации навыков (например, C++/C#)
- слишком “плоский” профиль (нет skills/experience, только общий текст)

### 10.2 SQL диагностика (примеры)

**Вакансии без skill требований:**

SELECT v.id, v.title  
FROM vacancies v  
LEFT JOIN vacancy_requirements r  
  ON r.vacancy_id=v.id AND r.kind='skill'  
WHERE r.id IS NULL;

**Вакансии с низким quality_score:**

SELECT v.id, v.title, vp.quality_score  
FROM vacancy_parsed vp  
JOIN vacancies v ON v.id=vp.vacancy_id  
ORDER BY vp.quality_score ASC  
LIMIT 20;

**Топ рекомендаций для профиля:**

SELECT vacancy_id, final_score, verdict  
FROM vacancy_scores  
WHERE profile_id=1  
ORDER BY final_score DESC  
LIMIT 20;

---

## 11) Будущие улучшения (roadmap)

- **[NEXT]** Генерация резюме/cover-letter через LLM на основе tailoring + evidence
- **[NEXT]** Более строгие eligibility-фильтры (опыт, формат, зарплата)
- **[FUTURE]** Калибровка порогов и весов на размеченных данных (Precision@K)
- **[FUTURE]** Персонализация скоринга по фидбэку пользователя
- **[FUTURE]** Hybrid retrieval: BM25 + vector + reranker


# Импорт вакансий HeadHunter и нормализация текста (vacancy_import.md)

**Статус:** **[NOW]** реализован полный пайплайн импорта вакансий из HH с нормализацией HTML → `vacancy_parsed` (plain_text + sections_json + quality_score), извлечением требований `vacancy_requirements` (must/nice/constraints), пересчётом embeddings v2 и запуском мэтчинга.  
**[NEXT]** — расширение словарей/маркеров и улучшение качества секционирования.  
**[FUTURE]** — LLM-assisted extraction как опциональный режим.

---

## 1) Цель и ключевая проблема исходных данных HH

HH-описание вакансии часто приходит в формате **HTML** и содержит:

- теги `p/ul/li/br/strong`, вложенные списки
- “шум”: приветствия, рекламные блоки, общие фразы, повторяющиеся описания компании
- неструктурированный текст требований

Дополнительно HH может возвращать `key_skills`, но:

- они часто неполные
- не разделены на must-have / nice-to-have
- отсутствуют ограничения (релокация/формат/опыт) в виде явных полей

**Решение проекта:** вводится отдельный слой **`vacancy_parsed`**, который хранит очищенный текст и структуру секций вакансии. Это позволяет:

- устойчиво извлекать требования из текста
- хранить версионирование парсера (reproducibility)
- делать backfill/repair при улучшении логики

---

## 2) Сущности и таблицы, участвующие в импорте

### 2.1 `vacancies` — сырой слой

Содержит исходную вакансию и метаданные:

- title, company, location, salary, currency, url, status
- `description` — HTML (как пришло с HH)
- `source='hh'`, `external_id`

### 2.2 `vacancy_parsed` — нормализованный слой (**ключевой**)

**1:1 к вакансии**

- `vacancy_id` (PK/FK)
- `plain_text` — очищенный текст без HTML шума
- `sections_json` — JSON со структурой секций (см. ниже)
- `extracted_at`, `version`, `quality_score`

### 2.3 `vacancy_requirements` — требования вакансии

**1:N к вакансии**

- `kind`: `skill` или `constraint`
- `raw_text`, `normalized_key`
- `is_hard`, `weight` (must/nice)
- используется мэтчингом и explainability

---

## 3) API и фоновые задачи импорта

### 3.1 Основной endpoint импорта (асинхронно) — **[NOW]**

- `POST /api/v1/import/hh`

Запускает задачу импорта в Celery (возвращает `task_id`).

Типичные параметры:

- `text` — строка запроса
- `area` — регион
- `per_page`, `pages_limit`
- `fetch_details=true` — важно для получения полного description

### 3.2 Доп. endpoint clusters — **[NOW] если используется**

- `POST /api/v1/import/hh/clusters`

Используется для анализа параметров поиска (опционально).

### 3.3 Backfill/repair парсинга — **[NOW]**

- `POST /api/v1/dev/vacancies/hh/backfill-parsed?limit=...&only_missing=true`

Запускает перепарсинг `vacancy_parsed` и пересоздание `vacancy_requirements` (и, при настройке, пересчёт embeddings).

### 3.4 Статус задач

- `GET /api/v1/tasks/{task_id}`

---

## 4) Нормализация HTML → plain_text

### 4.1 Задача очистки HTML

Цель — получить текст, пригодный для:

- выделения секций по заголовкам,
- построчного анализа требований (каждый буллет — отдельная строка),
- семантического embedding (без мусора).

### 4.2 Правила преобразования

При очистке:

- `<li>` → отдельная строка (bullet line)
- `</p>`, `<br>` → перенос строки
- `<strong>` удаляется как тег, но текст сохраняется
- HTML entities декодируются (`&nbsp;` и т.п.)
- нормализуются пробелы и переносы строк
- удаляются повторяющиеся пробелы, пустые строки

**Результат:** `plain_text` — текст, где требования часто идут построчно.

---

## 5) Выделение секций вакансии (sections_json)

### 5.1 Структура `sections_json`

Хранится единый JSON-объект:

{  
  "responsibilities": {"lines": [...], "text": "..."},  
  "requirements": {"lines": [...], "text": "..."},  
  "nice_to_have": {"lines": [...], "text": "..."},  
  "conditions": {"lines": [...], "text": "..."},  
  "other": {"lines": [...], "text": "..."},  
  "meta": {"low_quality": false}  
}

- `lines` — список строк (буллетов), очищенных от маркеров и нумерации
- `text` — склеенный текст секции (для удобства)

### 5.2 Как выделяются секции

Парсер идёт по строкам `plain_text`, поддерживая `current_section`.  
При встрече заголовка (например, “Требования:”) переключает `current_section`.

**Заголовки секций распознаются по словарю маркеров** (RU+EN), например:

- requirements: “требования”, “мы ожидаем”, “квалификационные требования”, “requirements”
- responsibilities: “обязанности”, “задачи”, “responsibilities”
- nice_to_have: “будет плюсом”, “желательно”, “nice to have”
- conditions: “условия”, “мы предлагаем”, “benefits”

> **[NEXT]** расширение списка заголовков под нетипичные формулировки (например “Что важно”, “Skills”, “Expectations”).

---

## 6) Классификация строк: must/nice/other (маркеры требований)

### 6.1 Зачем это нужно

Даже внутри `requirements` и `nice_to_have` встречаются смешанные формулировки.  
Мы классифицируем каждую строку, чтобы:

- hard (must-have) влияли на eligibility/итоговый score,
- nice-to-have давали подсказки “что добавить”.

### 6.2 Маркеры must-have (пример)

RU:

- “обязательно”, “необходимо”, “требуется”, “нужно”, “обязателен”, “не менее”  
    EN:
- “must”, “required”, “mandatory”, “solid knowledge”, “proficiency in”

### 6.3 Маркеры nice-to-have (пример)

RU:

- “будет плюсом”, “желательно”, “приветствуется”, “как преимущество”, “не обязательно”  
    EN:
- “nice to have”, “would be a plus”, “preferred”, “optional”

### 6.4 Правило приоритета

1. Если current_section = nice_to_have → **nice**
2. Если current_section = requirements → **must** (если нет явного nice-marker)
3. Если строка содержит nice-marker → **nice**
4. Если строка содержит must-marker → **must**
5. Если строка начинается с “опыт/умение/знание/владение/понимание” → **must**
6. иначе → **other**

---

## 7) Извлечение требований `vacancy_requirements`

### 7.1 Типы требований

- `kind="skill"` — навыки/технологии/компетенции
- `kind="constraint"` — ограничения (опыт, график, занятость, локация, релокация)

### 7.2 Must vs Nice

- `is_hard=true`, `weight=3` для must
- `is_hard=false`, `weight=1` для nice

### 7.3 Источники требований

Система объединяет несколько источников:

1. `sections_json.requirements.lines` → hard skills
2. `sections_json.nice_to_have.lines` → nice skills
3. fallback extraction по `other` и всему `plain_text` (если мало skills)
4. HH `key_skills` (если есть) → nice, но не понижает hard, если уже найден hard

### 7.4 Нормализация навыков

Каждый skill сохраняется как:

- `raw_text` — каноническое имя (из словаря навыков или найденного выражения)
- `normalized_key` — нормализованный ключ для мэтчинга  
    **Важно:** сохраняются символы `+`, `#`, `.`, `-` (чтобы `c++`, `c#`, `node.js` не ломались).  
    **[NOW]** это критично для корректного ATS.

### 7.5 Fallback логика

Если после обработки requirements/nice секций найдено слишком мало навыков (например `< 3`):

- извлекаем навыки по всему `plain_text`
- маркеры must/nice внутри строк учитываются
- добавляется метка в `sections_json.meta.low_quality=true` и/или warning

---

## 8) quality_score: оценка качества парсинга вакансии

`quality_score` — эвристическая метрика 0..1, показывающая качество выделения секций и “насыщенность” текста.

Примерная логика:

- +0.35 если `requirements.lines >= 3`
- +0.15 если `responsibilities.lines >= 1`
- +0.10 если `conditions.lines >= 1`
- +0.20 если длина plain_text >= 600
- +0.20 если суммарно lines >= 8
- cap на 1.0

Использование `quality_score`:

- диагностика импорта и парсинга
- **quality-guard** в мэтчинге:
    - низкий score → ограничение verdict/скоринга
    - предупреждения в explanation

---

## 9) Идемпотентность и обновление данных (важно для повторных импортов)

При повторном импорте той же вакансии (same external_id):

- `vacancies` обновляется UPSERT’ом
- `vacancy_parsed` обновляется UPSERT’ом (обновляются plain_text/sections/score/version/extracted_at)
- `vacancy_requirements` пересоздаются (удаление старых auto-generated и вставка новых)

Это гарантирует:

- отсутствие дублей
- возможность улучшать парсер и “починить” существующую базу через backfill

---

## 10) Интеграция импорта с embeddings и мэтчингом

После успешного импорта и парсинга:

1. пересчитываются embeddings вакансий v2:
    - текст берётся из `vacancy_parsed.plain_text` (а не из HTML)
2. при необходимости пересчитывается мэтчинг:
    - либо по saved searches,
    - либо по запросу (recompute recommendations)

---

## 11) Диагностика и проверочные SQL-запросы

### 11.1 Проверить, что у каждой вакансии есть `vacancy_parsed`

SELECT  
  (SELECT count(*) FROM vacancies WHERE source='hh') AS hh_vacancies,  
  (SELECT count(*) FROM vacancy_parsed vp JOIN vacancies v ON v.id=vp.vacancy_id WHERE v.source='hh') AS hh_parsed;

### 11.2 Вакансии с низким quality_score

SELECT v.id, v.title, vp.quality_score  
FROM vacancy_parsed vp  
JOIN vacancies v ON v.id=vp.vacancy_id  
ORDER BY vp.quality_score ASC  
LIMIT 20;

### 11.3 Сколько вакансий имеют requirements.lines > 0

SELECT  
  count(*) FILTER (  
    WHERE jsonb_array_length(coalesce(sections_json->'requirements'->'lines','[]'::jsonb)) > 0  
  ) AS with_requirements,  
  count(*) AS total  
FROM vacancy_parsed;

### 11.4 Вакансии без skill requirements (должно быть мало)

SELECT v.id, v.title  
FROM vacancies v  
LEFT JOIN vacancy_requirements r  
  ON r.vacancy_id=v.id AND r.kind='skill'  
WHERE v.source='hh' AND r.id IS NULL  
LIMIT 50;

### 11.5 Сводка требований (skills vs constraints)

SELECT kind, count(*) AS cnt,  
       sum(CASE WHEN is_hard THEN 1 ELSE 0 END) AS hard_cnt  
FROM vacancy_requirements  
GROUP BY kind;

---

## 12) Типичные проблемы и как их исправлять

### Проблема A: requirements.lines = 0 почти у всех

Причины:

- заголовки секций слишком узко заданы
- заголовок “слипся” со строкой (например “Требования: опыт…”)

Решение:

- расширить список заголовков
- обрабатывать “header: content” (разделять двоеточием)

### Проблема B: слишком мало извлечённых skills

Причины:

- словарь навыков узкий
- тексты на смеси RU/EN
- нестандартные названия технологий

Решение:

- расширять словарь навыков и алиасы
- включать fallback extraction по whole plain_text

### Проблема C: ложные релокации (“переезд на Go”)

Причина:

- эвристика релокации по слову “переезд” без контекста

Решение:

- исключающие паттерны: “переезд на <технологию>”
- релокация = “релокац”, “переезд в”, “готовность к переезду”

### Проблема D: C++/C# ломаются в normalized_key

Причина:

- агрессивная нормализация (удаление `+`/`#`)

Решение:

- сохранять `+` и `#` в normalize_skill
- тесты на `c++`, `c#`, `node.js`

---

## 13) Roadmap улучшений (import/parsing)

- **[NEXT]** расширение маркеров заголовков секций (RU/EN)
- **[NEXT]** расширение словаря технологий + алиасы
- **[NEXT]** улучшение quality_score и quality-guard в мэтчинге
- **[FUTURE]** опциональный LLM-parsing требований (только как fallback при низком quality_score)
- **[FUTURE]** поддержка дополнительных источников вакансий

---

## 14) Минимальный чек-лист “импорт работает корректно”

Импорт считается корректным, если:

1. `vacancy_parsed` есть для каждой HH вакансии
2. У большинства вакансий `requirements.lines > 0`
3. `vacancy_requirements(kind='skill')` заполнены и содержат both hard/nice
4. `quality_score` коррелирует с реальным качеством (низкий там, где секции не выделились)
5. embeddings v2 считаются по `plain_text`
6. backfill способен “починить” старые вакансии без ручной чистки

# Embeddings (v2): fastembed + pgvector и семантический слой рекомендаций

**Статус:** **[NOW]** в проекте используется **fastembed** (без torch) и хранение эмбеддингов в PostgreSQL через **pgvector**, таблицы `vacancy_embeddings_v2` и `profile_embeddings_v2`, а также HNSW индексы для ускорения поиска. Семантический слой применяется в мэтчинге как компонент финального скоринга и/или как способ сформировать candidate set вакансий.  
**[NEXT]** — оптимизация батчей и кэширование, а также привязка эмбеддингов к версиям резюме (по желанию).  
**[FUTURE]** — hybrid retrieval (BM25 + vector) и reranker.

---

## 1) Назначение embeddings слоя

Embeddings слой решает две задачи:

1. **Семантическая релевантность**  
    Позволяет находить вакансии, которые подходят по смыслу, даже если формулировки различаются.
2. **Эффективность мэтчинга**  
    Вместо того чтобы детально сравнивать профиль со всеми вакансиями, можно:
    - взять top-N похожих вакансий по embeddings,
    - затем применить ATS/eligibility и финальный скоринг.

Важно: embeddings **не заменяют** ATS-слой требований, а дополняют его.

---

## 2) Провайдер и модель

### 2.1 Fastembed

В проекте выбран fastembed, потому что:

- **быстрее и легче** в сборке контейнеров (без torch),
- хорошо работает на CPU,
- простая интеграция.

### 2.2 Выбор модели

Модель должна поддерживать RU/EN и выдавать фиксированную размерность `EMBEDDING_DIM`.

Рекомендуемые настройки в env (примерно):

- `EMBEDDING_PROVIDER=fastembed`
- `EMBEDDING_MODEL_NAME=<имя модели>`
- `EMBEDDING_DIM=<dim>` _(если в проекте требуется явно; иначе можно брать из модели)_

> Требование консистентности: `EMBEDDING_DIM` в коде и размерность vector-колонки в БД должны совпадать.

---

## 3) Хранение эмбеддингов в БД (v2)

### 3.1 Таблицы

- `vacancy_embeddings_v2`
    - `vacancy_id` + `embedding vector(dim)`
- `profile_embeddings_v2`
    - `profile_id` + `embedding vector(dim)`

Почему v2:

- при смене модели/размерности безопаснее создать новую таблицу,
- можно хранить и сравнивать несколько поколений embeddings, не ломая старые данные.

### 3.2 Индексация

Для ускорения поиска используется **HNSW индекс** по колонке embedding.

Типовой смысл:

- быстрый approximate nearest neighbors (ANN)
- для top-N похожих объектов

---

## 4) Формирование текста для embeddings

Ключевой фактор качества embeddings — **какой текст мы кодируем**.

### 4.1 Вакансия: `Vacancy Document`

**Источники:**

- `vacancies.title`
- `vacancy_parsed.plain_text` (**основной**)
- опционально: ключевые требования (`vacancy_requirements`) в виде “Requirements: ...”

**Почему не HTML:**  
HTML-описание содержит шум, который ухудшает векторизацию. Поэтому берётся нормализованный `plain_text`.

**Рекомендованный формат:**

- Title + Company + Location
- Plain text (обязанности/требования/условия)
- Короткий список extracted skills

> Чем стабильнее “документ вакансии”, тем стабильнее similarity.

---

### 4.2 Профиль: `Profile Document`

Профильный текст должен отражать реальную сущность кандидата, а не только один абзац.

**Источники:**

- `profiles.title/headline`, `profiles.summary_about`
- `profile_skills` (особенно primary)
- `profile_experiences` (последние 3–5): position/company + achievements + stack
- `profile_projects` (последние 3)
- `profile_achievements` (топ 5)
- `profile_education`, `profile_certificates`, `profile_languages` (кратко)
- активная `resume_versions` (approved) или fallback `profiles.resume_text`

**Рекомендованный принцип:**

- сначала high-signal сущности (skills, achievements),
- затем контекст (experience/projects),
- ограничение длины (например 8–12k символов), чтобы не размывать смысл шумом.

---

## 5) Жизненный цикл embeddings

### 5.1 Когда пересчитываются embeddings

- после импорта вакансий из HH и заполнения `vacancy_parsed`
- после изменения профиля (skills/experience/resume_versions) — пересчитать `profile_embeddings_v2`

Рекомендуется делать пересчёт через фоновые задачи (Celery), чтобы не блокировать API.

### 5.2 Идемпотентность

Пересчёт embeddings должен:

- удалять/перезаписывать старую запись v2 для сущности
- создавать ровно 1 актуальную запись на profile/vacancy (если выбран такой дизайн)
- сохранять (опционально) model_name/версию модели

---

## 6) Использование embeddings в мэтчинге

### 6.1 Candidate set

Обычно схема такая:

1. получить `profile_embedding_v2`
2. найти top-N ближайших `vacancy_embeddings_v2`
3. для этих N вакансий выполнить полную оценку: eligibility → ATS → final score

Это уменьшает вычисления и ускоряет пересчёт рекомендаций.

### 6.2 Semantic score как компонент финального скоринга

Semantic score (0..1) входит в итоговую формулу, например:  
`final = 0.45*semantic + 0.35*hard + 0.20*nice`

> Если embeddings отсутствуют (нет записи в v2) — semantic=0, и это должно быть видно в explanation.

---

## 7) Производительность и батчирование

### 7.1 Батчирование

Fastembed выгодно прогонять не по 1 тексту, а батчами:

- вакансии: батчи 32–128
- профили: обычно 1–10 за раз

### 7.2 Кэширование модели

Модель fastembed должна загружаться 1 раз на процесс worker/api:

- singleton provider
- не пересоздавать TextEmbedding на каждый вызов

### 7.3 Ограничение длины текста

Слишком длинные тексты:

- замедляют генерацию embeddings
- добавляют шум

Решение:

- ограничить длину doc string
- не включать повторяющиеся куски (“о компании” много раз)

---

## 8) Проверка корректности (диагностика)

### 8.1 Проверить количество embeddings

SELECT  
  (SELECT count(*) FROM vacancy_embeddings_v2) AS vacancies_v2,  
  (SELECT count(*) FROM profile_embeddings_v2) AS profiles_v2;

### 8.2 Проверить, что embeddings v2 покрывают vacancy_parsed

SELECT  
  (SELECT count(*) FROM vacancy_parsed) AS parsed,  
  (SELECT count(*) FROM vacancy_embeddings_v2 ve  
     JOIN vacancy_parsed vp ON vp.vacancy_id=ve.vacancy_id) AS embedded_from_parsed;

### 8.3 Быстрая sanity-проверка качества similarity

- профиль backend должен быть ближе к backend вакансиям, чем к frontend/design
- профиль дизайнер должен быть ближе к дизайнерским вакансиям

---

## 9) Типичные проблемы и решения

### Проблема A: semantic score везде одинаковый

Причины:

- тексты для embeddings слишком похожи (шаблонные/короткие)
- профили не заполнены (нет skills/experience)
- embeddings не пересчитаны после изменений

Решение:

- улучшить Profile Document builder
- backfill профилей
- пересчитать embeddings v2

### Проблема B: semantic = 0

Причины:

- нет записи profile_embeddings_v2 или vacancy_embeddings_v2
- mismatch dim в БД и модели

Решение:

- пересчитать embeddings
- проверить `EMBEDDING_DIM` и vector-колонки

### Проблема C: embeddings сильно “шумят”

Причина:

- в документ включены слишком длинные/общие тексты
- не удалён HTML шум

Решение:

- использовать `vacancy_parsed.plain_text`
- ограничить размер текста и исключить “о компании/бенефиты” при необходимости

---

## 10) Roadmap (embeddings)

- **[NEXT]** оптимизация батчирования и повторного использования модели
- **[NEXT]** хранение model_name/version в embeddings таблицах для аудита
- **[FUTURE]** embeddings по версиям резюме (`resume_versions`)
- **[FUTURE]** hybrid retrieval: BM25 + vector
- **[FUTURE]** reranker (cross-encoder) для top-50 кандидатов

---

## 11) Практический чек-лист “embeddings настроены правильно”

1. `vacancy_embeddings_v2` и `profile_embeddings_v2` заполнены
2. `EMBEDDING_DIM` совпадает с размерностью vector колонок
3. Vacancy embedding строится по `vacancy_parsed.plain_text`, а не по HTML
4. Profile embedding строится по нормализованным данным (skills/experience/projects)
5. Semantic score различает профили и профессии
6. Пересчёт выполняется батчами и в фоне (Celery)


# LLM и генерация документов (docs/llm.md)

**Статус:**

- **[NOW]** в системе уже есть версионность документов: `resume_versions`, `cover_letter_versions` и workflow _draft → edit → approve_.
- **[NEXT]** подключение LLM через единый интерфейс провайдеров (первый — **GigaChat**) и генерация резюме/писем на основе `tailoring` (результатов мэтчинга).
- **[FUTURE]** второй провайдер (**OpenAI**) + расширение возможностей (tool-calling, автоуточнения, автооценка качества).

---

## 1) Зачем нужен LLM в проекте

LLM используется **не для рекомендаций**, а для **подготовки документов**:

- генерация версии резюме и сопроводительного письма под конкретную вакансию;
- преобразование “tailoring” (keywords/missing/evidence) в связный, читаемый текст;
- создание drafts, которые пользователь подтверждает (human-in-the-loop).

**Важно:** решения о “подходит/не подходит” остаются за модулем мэтчинга (ATS + eligibility + embeddings). LLM — только генератор текста.

---

## 2) Базовые принципы (анти-галлюцинации)

Чтобы LLM не “придумывала” опыт и факты, система работает по правилам:

1. **LLM видит только факты**, извлечённые из базы:
    - skills с уровнями (`profile_skills`)
    - опыт/проекты/достижения (`profile_experiences/projects/achievements`)
    - approved resume_version (если есть)
    - evidence фрагменты из мэтчинга (`resume_evidence`)
2. **Запрещено добавлять новые факты**, которых нет во входных данных.
3. Если фактов не хватает, LLM должна вернуть блок:
    - `НУЖНО УТОЧНИТЬ:` список вопросов к пользователю.
4. Итог всегда создаётся как **draft** и требует подтверждения пользователем (`approve`).

---

## 3) Архитектура LLM слоя (вариант A)

### 3.1 Единый интерфейс провайдеров

В бэкенде вводится абстракция:

- `LLMClient.generate(request) -> response`

Где request включает:

- `messages[]` (system/user/assistant)
- `model`, `temperature`, `max_tokens`, `timeout`

А response включает:

- `text` (готовый текст)
- `provider`, `model`
- `usage` (если есть)
- `raw` (для отладки, без PII-логирования)

### 3.2 Фабрика провайдеров

Один входной метод, который выбирает провайдер по env:

- `LLM_PROVIDER=gigachat|openai`
- `get_llm_client()` возвращает singleton-провайдер (важно для кэша токена)

---

## 4) Провайдер GigaChat (первый)

### 4.1 Аутентификация и токены

GigaChat использует **access token**, который получается по OAuth2 и действует ограниченное время.

Ключевые требования реализации:

- хранить `access_token` в памяти процесса (api/worker) и обновлять заранее (например за 120 секунд до истечения);
- каждый запрос получения токена должен иметь `RqUID` (uuid4);
- обрабатывать ошибки `401/403/429/5xx` и делать контролируемые retry.

### 4.2 Конфигурация (env)

Рекомендуемые переменные окружения:

- `LLM_PROVIDER=gigachat`
- `LLM_MODEL=<название модели GigaChat>`
- `LLM_TEMPERATURE=0.2`
- `LLM_MAX_TOKENS=1200`

GigaChat:

- `GIGACHAT_AUTH_KEY=<Basic ключ>`
- `GIGACHAT_SCOPE=<scope>`
- `GIGACHAT_OAUTH_URL=...`
- `GIGACHAT_API_BASE=...`
- `GIGACHAT_VERIFY_SSL=true|false`

> Секреты хранятся только на backend/worker (не на фронте).

### 4.3 Политика логирования

- Не логировать full prompt/резюме/письмо/контакты.
- Логировать только метаданные: provider, model, статус, время, размер ответа.

---

## 5) Будущий провайдер OpenAI (переключаемый)

**[FUTURE]** Второй провайдер добавляется без изменения бизнес-логики:

- реализуется `OpenAIClient` с тем же интерфейсом `LLMClient`;
- ключ берётся из `OPENAI_API_KEY`;
- провайдер выбирается через `LLM_PROVIDER=openai`.

**Важно:** переключение провайдера не должно менять:

- формат prompts,
- workflow сохранения drafts,
- API контракты docgen.

---

## 6) Pipeline генерации документов

### 6.1 Входные данные

Генерация выполняется для (profile_id, vacancy_id) и использует:

**Профиль (facts):**

- summary/about, предпочтения формата работы, локация (не обязательно включать всё)
- skills с уровнями
- последние 3–5 опытов: роль/компания/обязанности/достижения/стек
- проекты и достижения (коротко)

**Вакансия (facts):**

- title, company, location
- `vacancy_parsed.sections_json` (особенно requirements/nice_to_have)

**Tailoring (из мэтчинга):**

- keywords_present, keywords_missing_must/nice
- keywords_to_add
- cover_letter_points
- evidence фрагменты

### 6.2 Prompt building (templates)

Система строит `messages[]`:

1. `system`: строгие правила (без выдумывания, использовать только факты)
2. `user`: структурированный JSON/текст с блоками:
    - Vacancy
    - Tailoring
    - Profile facts + evidence

### 6.3 Выход

- Для резюме: формат Markdown с секциями (Summary/Skills/Experience/Projects/Education)
- Для сопроводительного письма: 200–350 слов, 3–5 абзацев, 2–3 конкретных факта/evidence

Если данных недостаточно:

- вместо “придумывания” возвращается `НУЖНО УТОЧНИТЬ:` вопросы.

---

## 7) Хранение результатов: drafts и версионность

### 7.1 Таблицы документов

**Resume versions**

- `resume_versions`: `profile_id`, `vacancy_id (nullable)`, `title`, `content_text`, `format`, `source`, `status`, `created_at`, `approved_at`

**Cover letter versions**

- `cover_letter_versions`: `profile_id`, `vacancy_id (nullable)`, `title`, `subject`, `content_text`, `source`, `status`, `created_at`, `approved_at`

### 7.2 Workflow

1. `generate_*` создаёт новую запись со статусом `draft`, `source="ai"`.
2. Пользователь редактирует текст (PUT).
3. Пользователь подтверждает `approve`:
    - статус → `approved`
    - `approved_at = now()`

### 7.3 Метаданные генерации (**[NEXT]**)

Чтобы обеспечить воспроизводимость, полезно хранить:

- `provider`, `model`
- `prompt_version`
- `input_hash` (sha256 входных данных)
- `temperature`, `max_tokens`

Сейчас этих полей в таблицах нет (по текущей схеме), поэтому варианты:

- **[NEXT]** добавить поля миграцией;
- или временно хранить часть метаданных в `source`/`title` (не рекомендуется как долгосрочное решение).

---

## 8) API: генерация и управление документами

### 8.1 Текущие эндпоинты (версии документов) — **[NOW]**

(Названия могут отличаться; ориентир — `/docs`)

- `GET /profiles/{profile_id}/resume-versions`
- `POST /profiles/{profile_id}/resume-versions`
- `PUT /profiles/{profile_id}/resume-versions/{id}`
- `POST /profiles/{profile_id}/resume-versions/{id}/approve`

Аналогично для `cover-letter-versions`.

### 8.2 Эндпоинты генерации через LLM — **[NEXT]**

Рекомендуемые:

- `POST /profiles/{profile_id}/vacancies/{vacancy_id}/resume/generate`
- `POST /profiles/{profile_id}/vacancies/{vacancy_id}/cover-letter/generate`

Возвращают:

- либо `resume_version_id / cover_letter_version_id` (синхронно),
- либо `task_id` (если генерация вынесена в Celery).

---

## 9) Асинхронность (Celery) — рекомендуется

Генерация LLM может занимать время и зависеть от внешнего API, поэтому лучше запускать её в worker:

- `generate_resume_draft_task(profile_id, vacancy_id)`
- `generate_cover_letter_draft_task(profile_id, vacancy_id)`

API сразу возвращает `task_id`, фронт опрашивает `/tasks/{task_id}`.

---

## 10) Ограничения, безопасность, приватность

1. **Секреты** (GigaChat/OpenAI) — только в env backend/worker, не в git, не на фронте.
2. **PII**:
    - email/phone/telegram не должны уходить в LLM без необходимости;
    - если нужно — отправлять только по явному согласию пользователя.
3. **Логи**:
    - не писать `content_text` в логи;
    - логировать длину текста и ids.
4. **Rate limits**:
    - ограничить частоту генерации по профилю (например не чаще N раз в минуту);
    - при 429 применять backoff.

---

## 11) Тестирование и проверка качества

### 11.1 Unit проверки

- шаблоны prompts: есть запрет на выдумывание фактов
- “NУЖНО УТОЧНИТЬ” при недостатке evidence
- нормализация/обрезка входных данных (чтобы не улетать в огромные токены)

### 11.2 Интеграционные проверки

- generate создаёт `draft` запись
- approve переводит в approved
- при ошибке провайдера создаётся понятная ошибка (и не создаётся “пустой документ”)

### 11.3 Контроль “не галлюцинировать”

Минимальная эвристика:

- если в тексте резюме/письма появились компании/даты, которых нет во входных facts → флаг “подозрение на галлюцинацию” и требование ручной правки.

---

## 12) Roadmap (LLM)

- **[NEXT]** GigaChat provider + фабрика + docgen endpoints + Celery задачи
- **[NEXT]** хранение метаданных генерации (provider/model/prompt_version/input_hash)
- **[FUTURE]** OpenAI provider (переключаемый), Responses API
- **[FUTURE]** tool-calling: задавать пользователю вопросы, если данных не хватает
- **[FUTURE]** автоматическая оценка качества текста (структура, отсутствие выдуманных фактов)

# Frontend (React + Vite): интерфейс пользователя и сценарий демо (docs/frontend.md)

**Статус:**

- **[NOW]** реализованы основные страницы: просмотр вакансий, рекомендации, детали вакансии с блоком мэтчинга, Settings (управление профилем и связанными сущностями).
- **[NEXT]** интеграция LLM-генерации (GigaChat) в UI: кнопки Generate Resume / Cover Letter, редактор draft, approve.
- **[FUTURE]** воронка откликов (applications), авторизация/мультипрофильность, Telegram интерфейс.

---

## 1) Назначение фронтенда

Frontend предоставляет пользователю интерфейс для:

1. управления профилем (данные + предпочтения + опыт/проекты/навыки),
2. просмотра вакансий и рекомендаций,
3. анализа мэтчинга по конкретной вакансии (почему подходит/не подходит),
4. работы с документами (резюме и сопроводительные, версии, статусность).

---

## 2) Технологии

- **React** (SPA)
- **Vite** (dev server + сборка)
- Fetch/axios (в зависимости от реализации) для API запросов
- Простые UI-компоненты без тяжёлых библиотек (в текущем подходе)

---

## 3) Конфигурация и запуск

### 3.1 Dev запуск

Из папки frontend:

npm install  
npm run dev

Открыть:

- `http://localhost:5173`

### 3.2 API base URL

Используется переменная:

- `VITE_API_BASE_URL` (или аналог)

Пример:

- `VITE_API_BASE_URL=http://localhost:8000/api/v1`

> В демо-режиме авторизации нет: фронт работает с профилем **profile_id=1** как “текущий пользователь”.

---

## 4) Страницы и маршруты

### 4.1 `/vacancies` — список вакансий (**[NOW]**)

Функции:

- просмотр списка вакансий,
- базовые фильтры/поиск (если добавлены),
- переход на страницу вакансии по клику.

Данные:

- `GET /vacancies`

UI:

- карточки с названием, компанией, локацией, зарплатой (если есть).

---

### 4.2 `/recommendations` — рекомендованные вакансии (**[NOW]**)

Функции:

- загрузка рекомендаций для текущего профиля,
- запуск пересчёта рекомендаций (если есть кнопка),
- сортировка по `final_score`, фильтр по verdict (strong/ok/weak/reject).

Данные:

- `GET /profiles/{profile_id}/recommendations?limit=...`
- `POST /profiles/{profile_id}/recommendations/recompute?limit=...` (асинхронно)

UI:

- карточки вакансий + score/verdict
- быстрое объяснение: “missing must-have: …” (если выводится кратко)

---

### 4.3 `/vacancies/:id` — страница вакансии + мэтчинг (**[NOW]**)

Функции:

- показывать подробную информацию вакансии,
- показывать результат мэтчинга и explainability.

Данные:

- `GET /vacancies/{vacancy_id}`
- `GET /profiles/{profile_id}/vacancies/{vacancy_id}/tailoring`

UI блоки:

1. **Vacancy Details**
    - title, company, location, salary
    - описание (plain_text или HTML безопасно отрендеренный)
2. **Matching Summary**
    - verdict (strong/ok/weak/reject)
    - final_score
    - components (semantic/hard/nice), если выводятся
3. **Eligibility**
    - ok/reasons_failed/warnings
4. **ATS Keywords**
    - present / missing_must / missing_nice / uncertain
    - keywords_to_add
5. **Evidence**
    - список фрагментов профиля, подтверждающих навыки

**[NEXT]**: здесь появятся кнопки генерации документов:

- “Generate Resume”
- “Generate Cover Letter”

---

### 4.4 `/settings` — настройки профиля (**[NOW]**)

Цель: редактирование всех данных и настроек профиля.

Структура:

- Основное (full_name, title/headline, summary_about)
- Контакты (email, phone, telegram)
- Локация (country/city/metro)
- Легальные (citizenship, work_authorization_country, needs_sponsorship)
- Доступность (available_from, notice_period_days)
- Формат работы (remote_ok, relocation_ok, preferred_employment, preferred_schedule)
- Финансы (salary_min, salary_target, currency — если есть)
- Интересы/предпочтения (JSONB/TagInput: preferred_industries, preferred_tech, excluded_tech и т.д.)
- Team/process preferences (JSON editor)
- Нормализованные секции:
    - Skills
    - Experiences
    - Projects
    - Achievements
    - Education
    - Certificates
    - Languages
    - Links
- Документы:
    - Resume versions
    - Cover letter versions

Данные (паттерн CRUD):

- `GET/PUT /profiles/{profile_id}`
- `GET/POST/PUT/DELETE /profiles/{profile_id}/skills` и аналогично остальным сущностям
- `GET/POST/PUT /profiles/{profile_id}/resume-versions` и `approve`
- `GET/POST/PUT /profiles/{profile_id}/cover-letter-versions` и `approve`

UX-принципы:

- редактирование карточек по одной (не блокировать всю страницу),
- явный статус сохранения + ошибки,
- пустые поля видимы (placeholder).

---

### 4.5 `/documents` (опционально) (**[NEXT]**)

Если выделить отдельную страницу:

- список резюме/писем,
- фильтр по status (draft/approved),
- поиск по vacancy_id,
- история версий.

---

## 5) Компоненты UI (рекомендуемая структура)

### 5.1 Общие

- `Layout` (header/nav)
- `ErrorBanner`, `Toast`
- `LoadingSpinner`

### 5.2 Формы

- `TextField`, `TextAreaField`, `SelectField`, `SwitchField`, `DateField`
- `TagInput` (для массивов строк JSONB)
- `InlineEditorCard` (view/edit режим для одной записи)

---

## 6) Работа с задачами (async)

Если backend возвращает `task_id`:

- фронт должен опрашивать:
    - `GET /tasks/{task_id}`
- отображать:
    - статус (PENDING/STARTED/SUCCESS/FAILURE)
    - ошибка в случае FAILURE

Использование:

- импорт HH
- recompute recommendations
- **[NEXT]** генерация LLM документов (если вынесено в worker)

---

## 7) Сценарий демо (3–5 минут) — для защиты

### Шаги (текущий сценарий) **[NOW]**

1. `/settings`:
    - показать, что профиль нормализован (skills/experience/projects)
2. `/vacancies`:
    - показать список вакансий (в т.ч. импортированных HH)
3. `/recommendations`:
    - нажать “Recompute” (если нужно) и показать top вакансии
4. Открыть вакансию:
    - показать verdict + причины
    - показать missing must-have и evidence

### Расширенный сценарий **[NEXT]**

5. На странице вакансии нажать:
    - “Generate Cover Letter” → создаётся draft
6. Открыть draft в UI:
    - отредактировать
    - нажать Approve
7. Показать историю версий (draft → approved)

---

## 8) UX/качество и ожидаемое поведение

1. **Reject** вакансии не должны попадать в топ (сортировка учитывает eligibility).
2. В объяснении мэтчинга пользователь должен видеть:
    - какие must-have отсутствуют,
    - что можно добавить/подчеркнуть,
    - где в профиле это подтверждается (evidence).
3. Settings должен позволять заполнить профиль так, чтобы мэтчинг стал точнее:
    - levels навыков,
    - опыт и достижения,
    - локация/релокация/формат.

---

## 9) Ошибки и troubleshooting (frontend)

- CORS / неверный base URL: проверить `VITE_API_BASE_URL`
- 404 по эндпоинтам: сверить пути с `/docs`
- пустые рекомендации:
    - профиль не заполнен (нет skills/experiences)
    - не пересчитаны embeddings v2
    - не пересчитан мэтчинг

---

## 10) Roadmap по фронту

- **[NEXT]** UI генерации документов:
    - кнопки generate на вакансии
    - editor для draft
    - approve и история версий
- **[FUTURE]** Applications (воронка откликов) UI:
    - список откликов, статусы, заметки
- **[FUTURE]** Авторизация:
    - login/register
    - несколько профилей на пользователя
- **[FUTURE]** Telegram канал (как отдельный интерфейс)

# Тестирование и качество (docs/testing.md)

**Статус:**

- **[NOW]** есть тестовые данные (несколько профилей), импорт HH, пайплайн парсинга вакансий (`vacancy_parsed`) и мэтчинг (eligibility + ATS + semantic).
- **[NEXT]** — тестирование LLM генерации (GigaChat) и проверка “без галлюцинаций”.
- **[FUTURE]** — формальная оценка качества рекомендаций на размеченной выборке (Precision@K), нагрузочные тесты.

Документ описывает, что и как тестируется: от unit-тестов отдельных функций до интеграционных проверок пайплайна “импорт → parsing → requirements → embeddings → matching”.

---

## 1) Цели тестирования

1. **Корректность данных**: вакансии и профили нормализуются, требования извлекаются, embeddings строятся.
2. **Корректность мэтчинга**: must-have правильно выделяются, eligibility фильтры работают, verdict объясним и воспроизводим.
3. **Стабильность пайплайна**: повторные импорты не создают дублей, backfill исправляет старые данные.
4. **Производительность**: пересчёт embeddings и рекомендаций не занимает “неприемлемое” время.
5. **Безопасность**: секреты не утекут в логи, персональные данные не уходят “случайно” во внешние сервисы.

---

## 2) Уровни тестирования

### 2.1 Unit tests (функции/модули)

Тестируем “чистые” функции, которые имеют чёткий вход/выход:

- нормализация навыков (`normalize_skill`, `normalized_key`)
- токенизация и точный матчинг (границы слов)
- очистка HTML (`strip_html`)
- выделение секций и классификация строк must/nice (`is_section_header`, `classify_line`)
- эвристики eligibility (релокация с исключениями “переезд на Go”)

### 2.2 Integration tests (пайплайны)

Тестируем взаимодействие модулей и базы:

- импорт HH → заполнение `vacancies`, `vacancy_parsed`, `vacancy_requirements`
- backfill parsing → обновление `version`, `quality_score`
- пересчёт embeddings v2
- пересчёт recommendations → заполнение `vacancy_scores` и `resume_evidence`
- CRUD нормализованных таблиц профиля через API

### 2.3 End-to-end (ручные сценарии)

Демо-сценарии на UI:

- заполнить профиль в Settings
- импортировать вакансии
- получить рекомендации
- открыть вакансию и посмотреть explanation/evidence
- **[NEXT]** сгенерировать резюме/письмо → draft → approve

---

## 3) Набор тестовых данных (fixtures)

### 3.1 Профили

Используются 3–4 “контрастных” профиля:

- Backend (Python)
- Designer (graphic/UX)
- Project Manager
- (опционально) Junior Frontend

Это позволяет проверять:

- различимость профилей (semantic/ATS)
- корректность отсекающих правил (например relocation)

### 3.2 Вакансии

Два источника:

- `manual` вакансии (контрольные, короткие, полностью понятные)
- `hh` вакансии (реальные, HTML, шум, вариативность)

Важно иметь:

- 10–30 вакансий разных ролей (backend/front/design/pm)
- пару вакансий с “релокацией”
- пару вакансий с “переезд на технологию” (для проверки исключений)

---

## 4) Unit-тесты: что обязательно проверить

### 4.1 HTML → plain_text

**Проверки:**

- HTML теги удаляются
- `<li>` превращаются в отдельные строки
- переносы сохраняют структуру
- HTML entities декодируются

**Пример кейса:**

- вход: `<ul><li>Требования: Python</li><li>Docker</li></ul>`
- выход: две строки “Требования: Python” и “Docker”

---

### 4.2 Выделение секций вакансии

**Проверки:**

- заголовки “Требования/Обязанности/Условия/Будет плюсом” определяются независимо от регистра
- заголовок может быть в формате “Требования: …” (на одной строке)
- если заголовки не найдены, всё попадает в `other`

---

### 4.3 Классификация must/nice строк

**Проверки:**

- “обязательно/необходимо/требуется” → must
- “будет плюсом/желательно” → nice
- при активной секции nice_to_have всё считается nice
- при активной секции requirements по умолчанию must

---

### 4.4 Нормализация навыков (critical)

**Проверки:**

- `C++` остаётся `c++`, `C#` остаётся `c#` (не превращается в `c`)
- `Docker compose` и `docker-compose` нормализуются одинаково
- `Git` не матчится через `GitHub`
- алиасы: `DRF` ↔ `Django REST Framework`

---

### 4.5 Eligibility эвристики

**Проверки:**

- “релокация в …” → relocation_required=true
- “переезд на Go/архитектуру” → relocation_required=false (исключение)
- location mismatch / remote mismatch — корректные причины отказа

---

## 5) Интеграционные проверки (пошагово)

### 5.1 Импорт HH заполняет vacancy_parsed и requirements

**Критерии успешности:**

1. `vacancy_parsed` создан для каждой HH вакансии
2. `sections_json.requirements.lines` > 0 хотя бы у части вакансий
3. `vacancy_requirements(kind='skill')` не пустой
4. есть `is_hard=true` у требований, извлечённых из requirements секции

**SQL проверки:**

-- vacancy_parsed покрытие  
SELECT  
  (SELECT count(*) FROM vacancies WHERE source='hh') AS hh_vacancies,  
  (SELECT count(*) FROM vacancy_parsed vp JOIN vacancies v ON v.id=vp.vacancy_id WHERE v.source='hh') AS hh_parsed;

-- сколько вакансий имеют requirements.lines > 0  
SELECT  
  count(*) FILTER (WHERE jsonb_array_length(coalesce(sections_json->'requirements'->'lines','[]'::jsonb)) > 0) AS with_req,  
  count(*) AS total  
FROM vacancy_parsed;

---

### 5.2 Backfill обновляет version/quality_score

**Критерии:**

- после backfill `version` соответствует текущей версии парсера
- `extracted_at` обновляется
- число вакансий без skills уменьшается

---

### 5.3 Пересчёт embeddings v2

**Критерии:**

- `vacancy_embeddings_v2` покрывает большинство `vacancy_parsed`
- `profile_embeddings_v2` есть для каждого профиля

**SQL:**

SELECT  
  (SELECT count(*) FROM vacancy_embeddings_v2) AS vac_v2,  
  (SELECT count(*) FROM profile_embeddings_v2) AS prof_v2;

---

### 5.4 Пересчёт рекомендаций (vacancy_scores + evidence)

**Критерии:**

- для профиля создаются `vacancy_scores` на top-N вакансий
- `explanation.semantic.score` не нулевой (если embeddings есть)
- есть записи в `resume_evidence`

**SQL:**

SELECT count(*) FROM vacancy_scores WHERE profile_id=1;

SELECT count(*) FROM resume_evidence WHERE profile_id=1;

---

### 5.5 Различимость профилей (quality check)

Для трёх разных профилей top-10 вакансий должны отличаться:

- backend профиль → backend вакансии
- дизайнер → дизайн вакансии
- PM → PM вакансии

**Проверка:**

- сравнить топ-5 по `final_score` и убедиться, что “чужие” роли не попадают в strong.

---

## 6) Ручные сценарии (E2E) — чек-листы

### Сценарий A: рекомендации

1. Открыть Settings, заполнить skills/experience
2. Импортировать 1–2 страницы HH вакансий
3. Пересчитать рекомендации
4. Открыть top вакансию:
    - есть explanation
    - есть missing must-have
    - есть evidence

### Сценарий B: “reject” по релокации

1. Профиль: relocation_ok=false
2. Вакансия: текст содержит “релокация”
3. Мэтчинг должен вернуть:
    - eligibility.ok=false
    - verdict=reject

### Сценарий C: исключение “переезд на Go”

1. Вакансия содержит “переезд на Go”
2. relocation_required=false
3. не должно быть reject по релокации

---

## 7) Метрики качества (в дипломе и для контроля)

### 7.1 Precision@K (**[FUTURE]**, но можно сделать сейчас упрощённо)

- выбрать 30–50 пар (profile, vacancy)
- вручную разметить: pass/maybe/fail
- посчитать Precision@5, Precision@10 для каждого профиля

### 7.2 Coverage metrics (**[NOW]** полезно)

- доля вакансий с `requirements.lines > 0`
- доля вакансий с hard skills > 0
- доля рекомендаций с evidence > 0

### 7.3 Performance metrics (**[NOW]**)

- время импорта N вакансий
- время backfill N вакансий
- время пересчёта embeddings
- время recompute recommendations (limit=50)

---

## 8) Производительность: практические проверки

**Цели:**

- пересчёт рекомендаций для профиля на 50 вакансий должен быть быстрым
- embeddings в батчах ускоряют pipeline

**Что измерять:**

- логировать время выполнения tasks (Celery)
- фиксировать размеры батчей

---

## 9) Безопасность и приватность (тесты)

1. Проверить, что env-секреты (HH/LLM) не попадают:
    - в ответы API
    - в логи (особенно docker logs)
2. Проверить, что PII (телефон/почта):
    - не отправляется в LLM без необходимости (**[NEXT]**)
3. Проверить, что ошибки внешних API не “протекают” в виде stack traces наружу (500 → нормализованный error response)

---

## 10) Roadmap тестирования

- **[NEXT]** тесты для LLM генерации:
    - draft создаётся
    - approve работает
    - “не выдумывать факты” (heuristics)
- **[FUTURE]** автоматическая оценка качества текста документов (структура/тон/ключевые слова)
- **[FUTURE]** нагрузочные тесты (JMeter/Locust) для API:
    - импорт + рекомендации под нагрузкой
- **[FUTURE]** A/B тестирование весов скоринга

---

## 11) Минимальный критерий “готово” для демонстрации

Система готова к демонстрации, если:

1. HH импорт создаёт `vacancy_parsed` и `vacancy_requirements`
2. embeddings v2 заполнены
3. рекомендации различаются для разных профилей
4. в деталях вакансии есть explanation и evidence
5. reject по релокации работает, исключение “переезд на Go” работает
6. UI Settings позволяет наполнить профиль без ручных SQL

# Эксплуатация и развёртывание (docs/operations.md)

**Статус:**

- **[NOW]** проект разворачивается через `docker compose` (frontend + api + worker + beat + postgres(pgvector) + redis). Миграции Alembic применяются вручную командой.
- **[NEXT]** подключение LLM (GigaChat) потребует секретов в env и контроля логирования/PII, а также желательно вынести генерацию в Celery.
- **[FUTURE]** production деплой (reverse proxy/HTTPS), мониторинг, резервное копирование по расписанию, multi-user auth.

---

## 1) Требования к окружению

### 1.1 Локальная разработка / стенд

- Docker Engine
- Docker Compose
- Доступ к интернету (для HH API и LLM провайдера)

### 1.2 Production (перспектива)

- Linux host (VM/сервер)
- Docker + Compose (или Kubernetes)
- Reverse proxy (Nginx/Traefik) + HTTPS
- Хранилище секретов (env/secret manager)

---

## 2) Сервисы docker-compose

В типовой конфигурации запускаются:

- `jobsearch_frontend` — React UI (Vite dev/prod)
- `jobsearch_api` — FastAPI backend
- `jobsearch_worker` — Celery worker (фоновые задачи)
- `jobsearch_beat` — Celery beat (периодические задачи)
- `jobsearch_db` — PostgreSQL + pgvector (контейнер `pgvector/pgvector`)
- `jobsearch_redis` — Redis (broker для Celery)

**Назначение сервисов:**

- API обслуживает запросы UI и выдаёт `/docs`.
- Worker выполняет “тяжёлые” задачи: импорт вакансий, backfill parsing, embeddings, recompute recommendations, **[NEXT]** LLM generation.
- Beat запускает периодические задачи: синхронизацию saved searches и т.п.

---

## 3) Переменные окружения (env)

### 3.1 База данных и Redis

Типично:

- `DATABASE_URL` (или `POSTGRES_*` в compose)
- `REDIS_URL`

### 3.2 Embeddings / pgvector

- `EMBEDDING_PROVIDER=fastembed`
- `EMBEDDING_MODEL_NAME=...`
- `EMBEDDING_DIM=...` _(если требуется явно)_
- (опционально) `EMBEDDING_BATCH_SIZE`

### 3.3 HeadHunter импорт

- параметры rate limit/таймаутов (если вынесены)
- настройки периодической синхронизации saved searches

### 3.4 LLM (GigaChat) — **[NEXT]**

- `LLM_PROVIDER=gigachat`
- `LLM_MODEL=...`
- `LLM_TEMPERATURE=0.2`
- `LLM_MAX_TOKENS=1200`
- `GIGACHAT_AUTH_KEY=...`
- `GIGACHAT_SCOPE=...`
- `GIGACHAT_OAUTH_URL=...`
- `GIGACHAT_API_BASE=...`
- `GIGACHAT_VERIFY_SSL=true|false`

**Правило безопасности:**

- ключи и токены не коммитятся в репозиторий;
- `GIGACHAT_AUTH_KEY` хранится только на backend/worker.

---

## 4) Стандартный порядок запуска

Из директории `infra/`:

docker compose up -d --build

Проверка статуса:

docker compose ps

---

## 5) Миграции базы данных (Alembic)

### 5.1 Применение миграций

После сборки/старта контейнеров:

docker compose exec api alembic upgrade head

### 5.2 Проверка состояния миграций

docker compose exec api alembic current  
docker compose exec api alembic heads

Ожидается: `current` и `heads` показывают одну и ту же ревизию.

### 5.3 Если схема “разъехалась”

- для диагностики: посмотреть `alembic_version` в БД:

docker compose exec db psql -U jobuser -d jobdb -c "select version_num from alembic_version;"

**Важно:** `alembic stamp head` использовать только в крайнем случае, когда схема уже вручную приведена и нужно синхронизировать версию.

---

## 6) Управление жизненным циклом данных

### 6.1 Seed / тестовые профили

Для демонстрации рекомендуется:

- иметь несколько профилей (backend/designer/pm)
- фиксировать `profile_id` для демо (например 1)

Сиды можно добавлять:

- SQL скриптами
- dev endpoints
- через Settings UI

### 6.2 Очистка данных (dev)

Для полной очистки вакансий и зависимостей:

TRUNCATE TABLE vacancies RESTART IDENTITY CASCADE;

> Это удалит связанные: requirements, embeddings, scores, evidence, vacancy_parsed и т.п.

---

## 7) Фоновые задачи (Celery)

### 7.1 Проверка логов

docker compose logs -f worker  
docker compose logs -f beat  
docker compose logs -f api

### 7.2 Статус задач

Если API поддерживает:

- `GET /api/v1/tasks/{task_id}`

Это важно для:

- HH import
- backfill parsing
- rebuild embeddings
- recompute recommendations
- **[NEXT]** генерация документов LLM

---

## 8) Мониторинг и логирование

### 8.1 Логи

Рекомендуемый минимум:

- логировать статус операций (начало/конец) и длительность
- логировать ошибки внешних API (HH/LLM) без утечки PII

### 8.2 PII и безопасность

- не логировать:
    - `resume_text`, `content_text` документов
    - `phone`, `email`
- логировать только:
    - `profile_id`, `vacancy_id`, `task_id`
    - `provider/model`, время, размер ответа

---

## 9) Резервное копирование и восстановление (backup/restore)

### 9.1 Backup (pg_dump)

docker compose exec db pg_dump -U jobuser -d jobdb > backup_jobdb.sql

### 9.2 Restore

cat backup_jobdb.sql | docker compose exec -T db psql -U jobuser -d jobdb

**Production рекомендация:** делать backup по расписанию (cron) и хранить копии отдельно от сервера.

---

## 10) Частые проблемы и решения

### 10.1 “db is unhealthy” / права на initdb

Причина часто в том, что bind-mount папки init имеет неподходящие права на host/VM.  
Решение:

- убрать/не монтировать `docker-entrypoint-initdb.d` с хоста
- хранить проект на нормальной FS (ext4) внутри VM
- использовать COPY init файлов внутрь образа (если нужно)

### 10.2 Долгий build образов

Причины:

- тяжёлые зависимости (torch — уже убрали)
- отсутствие кэширования pip слоёв

Решение:

- dependency слой в Dockerfile отдельно (копировать requirements до кода)
- buildkit cache pip

### 10.3 semantic score = 0

Причина:

- нет `profile_embeddings_v2` или `vacancy_embeddings_v2`  
    Решение:
- пересчитать embeddings через dev endpoint/таски
- проверить `EMBEDDING_DIM`

### 10.4 Мэтчинг “странный”

Причины:

- низкий `quality_score` у вакансии
- нет извлечённых hard requirements  
    Решение:
- backfill parsing + расширение маркеров заголовков + словарь навыков

---

## 11) Production deployment (перспектива) — **[FUTURE]**

### 11.1 Рекомендуемая схема

- Nginx/Traefik перед API и frontend
- HTTPS
- отдельные volumes для Postgres
- резервное копирование по расписанию
- мониторинг (Prometheus/Grafana) и алерты

### 11.2 Secrets management

- хранить ключи HH/LLM в secret manager или в защищённых env
- ограничить доступ к worker/api окружению

---

## 12) Операционный чек-лист

Перед демо/деплоем:

1. `docker compose ps` — все сервисы healthy
2. `alembic upgrade head` выполнено
3. в БД есть тестовые профили и вакансии
4. `vacancy_parsed` заполнен, `vacancy_requirements` заполнен
5. embeddings v2 пересчитаны
6. recommendations пересчитаны
7. фронт открывается и показывает данные

Для LLM (**[NEXT]**):  
8) env ключи провайдера заданы  
9) генерация создаёт drafts и требует approve  
10) логи не содержат PII

# Roadmap / Дорожная карта проекта (docs/roadmap.md)

Документ фиксирует текущий статус, ближайшие задачи и перспективные направления развития проекта. Он нужен, чтобы:

- синхронизировать ожидания (что уже реализовано, что в разработке),
- обеспечить прозрачность MVP и границ проекта,
- использовать как раздел “перспективы развития” в ВКР.

---

## 1) Краткое описание продукта

Проект — система поддержки соискателя при поиске работы, построенная по принципу **“перевёрнутого ATS”**: рекомендации формируются на основе имитации работодателя (ATS → screening → scoring) с объяснением причин и подсказками по улучшению резюме/письма под конкретную вакансию.

---

## 2) Статус текущей версии (MVP+)

### 2.1 Что уже реализовано **[NOW]**

#### Данные вакансий

- Импорт вакансий из HH (асинхронно через Celery).
- Нормализация HTML-описания и выделение секций вакансии.
- Таблица `vacancy_parsed`:
    - `plain_text`
    - `sections_json`
    - `quality_score`, `version`, `extracted_at`
- Извлечение требований в `vacancy_requirements`:
    - `skill` и `constraint`
    - `must-have (is_hard=true, weight=3)` / `nice-to-have (weight=1)`
- Backfill/repair для перепарсинга существующих вакансий.

#### Профиль пользователя (нормализация)

- Расширенная таблица `profiles` (контакты, локация, предпочтения, доступность, легальные поля).
- Набор нормализованных таблиц:
    - `profile_experiences`, `profile_projects`, `profile_achievements`
    - `profile_education`, `profile_certificates`
    - `profile_skills` (уровни, годы, evidence), `profile_languages`, `profile_links`
- Seed/фикстуры: несколько профилей (backend, designer, pm) для тестов/демо.

#### Embeddings и векторный поиск

- Замена torch → **fastembed** (CPU friendly).
- Таблицы embeddings v2:
    - `vacancy_embeddings_v2`, `profile_embeddings_v2`
- Использование `vacancy_parsed.plain_text` при построении embedding вакансий.
- Индексация через pgvector/HNSW.

#### Мэтчинг и explainability

- Мэтчинг “перевёрнутого ATS”:
    - eligibility (hard filters)
    - ATS coverage must/nice
    - semantic score (embeddings)
    - итоговый score + verdict
- Explainability:
    - `vacancy_scores.explanation` (структурированный JSON)
    - `resume_evidence` (цитаты/доказательства)

#### Документы

- Версионность резюме и сопроводительных:
    - `resume_versions`, `cover_letter_versions`
    - статусы `draft/approved/archived`

#### UI (frontend)

- Просмотр вакансий.
- Просмотр рекомендованных вакансий.
- Страница вакансии с деталями мэтчинга (explanation/evidence).
- Settings: редактирование профиля и нормализованных таблиц, управление версиями документов.

---

## 3) Ближайшие задачи (следующий релиз) **[NEXT]**

### 3.1 Подключение LLM и генерация документов (главный следующий блок)

**Цель:** автоматическая генерация резюме и письма по данным профиля и tailoring без галлюцинаций.

Задачи:

1. Единый интерфейс `LLMClient` + `factory`:
    - переключение провайдера через env
2. Провайдер **GigaChat**:
    - OAuth token caching (RqUID, refresh)
    - retry/backoff и обработка 401/429/5xx
3. Prompt builders:
    - строгий system prompt (“не выдумывать факты”)
    - вход только из facts + evidence
    - “НУЖНО УТОЧНИТЬ” при недостатке данных
4. DocumentGenerationService:
    - create draft resume_version / cover_letter_version
    - запись meta (provider/model/prompt_version/input_hash) _(если добавим поля или временно хранить иначе)_
5. API endpoints:
    - `/profiles/{id}/vacancies/{vid}/resume/generate`
    - `/profiles/{id}/vacancies/{vid}/cover-letter/generate`
6. UI:
    - кнопки Generate на странице вакансии
    - редактор draft + approve
7. Асинхронность:
    - запуск генерации в Celery, возврат `task_id`

**Критерии готовности:**

- генерация создаёт только draft, который можно approve
- текст не содержит фактов, которых нет во входных данных

---

### 3.2 Калибровка качества мэтчинга (минимальная оценка)

**Цель:** подготовить измеримое качество для ВКР и убедиться, что рекомендации “работают”.

Задачи:

- собрать 30–50 пар (profile, vacancy)
- разметить pass/maybe/fail
- измерить Precision@5 / Precision@10
- откалибровать пороги verdict и веса (semantic/hard/nice)

---

### 3.3 Улучшения парсинга вакансий (точечные)

Задачи:

- расширить заголовки секций и маркеры must/nice
- расширить словарь навыков + алиасы
- улучшить quality_score и quality-guard (например ограничивать strong при low-quality)

---

## 4) Среднесрочные задачи (после следующего релиза) **[FUTURE]**

### 4.1 Воронка откликов (applications)

**Цель:** управление процессом поиска работы, а не только рекомендациями.

Предлагаемые сущности:

- `applications` (profile_id, vacancy_id, status, created_at, updated_at)
- `application_status_history` (application_id, status, note, timestamp)
- `application_notes` / `tasks` (напоминания/контакты/собеседования)

UI:

- Kanban-воронка (Applied → HR screen → Tech interview → Offer/Reject)
- интеграция с документами (какое резюме/письмо отправлено)

---

### 4.2 Авторизация и мультипользовательский режим

**Цель:** полноценный продукт, а не демо с profile_id=1.

- `users` (email/password or SSO)
- связь users↔profiles (ownership)
- RBAC (минимально)
- хранение токенов (JWT/session)

---

### 4.3 OAuth HH для импорта профиля

**Цель:** импортировать резюме/опыт пользователя напрямую из HH.

- OAuth 2.0 flow
- импорт резюме → заполнение profile_* таблиц
- согласие пользователя на обработку данных

---

### 4.4 Дополнительные источники вакансий

- LinkedIn (если доступно), агрегаторы, RSS/парсинг
- единый интерфейс importers

---

### 4.5 OSINT-обогащение (опционально, осторожно)

**Цель:** дополнительные сигналы по компании/вакансии, но с учётом этики и правовых рисков.

- хранение внешних источников и признаков достоверности
- настройки отключения (privacy)

---

### 4.6 Улучшение ранжирования: hybrid retrieval + reranker

- BM25 (текстовый поиск) + embeddings
- reranker (cross-encoder) для top-50

---

## 5) Порядок приоритетов (по ценности)

1. **LLM DocGen (GigaChat) + UI + draft/approve** — максимальная “видимая” ценность для пользователя и сильный блок для ВКР
2. **Калибровка качества мэтчинга (Precision@K)** — измеримость и доказательство эффективности
3. **Улучшение парсинга вакансий** — напрямую повышает качество ATS
4. **Applications funnel** — превращает систему в “продукт поиска работы”
5. **Auth + OAuth HH** — масштабирование на реальных пользователей
6. Остальные улучшения (источники, hybrid, OSINT)

---

## 6) Риски и меры снижения

### 6.1 Риск: LLM галлюцинирует факты

Меры:

- вход только facts + evidence
- “НУЖНО УТОЧНИТЬ” вместо выдумывания
- human-in-the-loop approve

### 6.2 Риск: низкое качество extraction вакансий

Меры:

- `vacancy_parsed` + quality_score
- backfill и версия парсера
- расширение словаря и маркеров

### 6.3 Риск: производительность

Меры:

- fastembed вместо torch
- батчи embeddings
- candidate set по embeddings перед ATS

---

## 7) Список “готово для защиты” (Definition of Done)

Система считается готовой к демонстрации, если:

1. импорт HH даёт `vacancy_parsed` и `vacancy_requirements`
2. embeddings v2 заполнены
3. рекомендации отличаются для разных профилей
4. на странице вакансии есть explanation + evidence
5. **[NEXT]** генерируются drafts резюме/письма и работает approve
6. есть краткая метрика качества (хотя бы ручная оценка топ-10)
