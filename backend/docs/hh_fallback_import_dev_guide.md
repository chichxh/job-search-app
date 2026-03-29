# HH fallback JSON import: fixtures + dev guide

Этот документ фиксирует **canonical contract** и reproducible flow для импорта профиля из HH-like JSON через fallback endpoint `POST /api/v1/integrations/hh/import-json`.

## Canonical fixtures

Используйте эти примеры как baseline для разработки, тестов и демо:

- `backend/tests/fixtures/hh/hh_profile_sample.json` — happy path envelope c `resumes` и двумя вариантами резюме.
- `backend/tests/fixtures/hh/hh_profile_edge_case.json` — edge-case payload с `resume`, salary `from/to`, mixed date formats.
- `backend/docs/examples/hh/*.json` — те же файлы для быстрого копирования в demo/docs context.

## Documented payload contract

Импортер ожидает JSON-object и поддерживает HH-like envelope:

- `me` *(optional)* — информация о пользователе HH; fallback importer не использует напрямую.
- `resumes_mine.items` *(optional)* — список доступных resume (в т.ч. для выбора `resume_id`).
- `resume` *(optional)* — single resume объект.
- `resumes` *(optional)* — массив resume объектов.
- также поддерживается payload, где корневой объект уже похож на resume (flat resume JSON).

Импортер сначала собирает кандидатов из `resume` / `resumes` / `resumes_mine.items`, затем:

1. если передан `resume_id`, ищет точное совпадение `id`;
2. иначе берёт первый resume с «полезным» содержимым (title/description/skills/skill_set/experience).

### Какие поля реально используются

Поля main profile:

- `first_name`, `last_name`, `middle_name` → `profiles.full_name`
- `title` → `profiles.title`
- `skills` / `summary` / `description` → `profiles.summary_about` (приоритет именно в таком порядке)
- `area.name` (или строка в `area`) → `profiles.location`, `profiles.city`
- `salary.amount` / `salary.from` / `salary.to` → `profiles.salary_min`
- `relocation.type` → `profiles.relocation_ok`
- `travel_time.id` → `profiles.remote_ok`
- `skill_set` → `profiles.skills_text`
- `description` → `profiles.resume_text`

Поля replace-per-section (delete + insert):

- `experience[]` → `profile_experiences`
- `skill_set[]` → `profile_skills`
- `language[]` → `profile_languages`
- `contact[]` → `profile_links`

### Какие поля optional

Практически все поля optional, но для успешного импорта нужен хотя бы один resume с полезным содержимым:

- непустой `description`, или
- непустой `title`, или
- непустой `skills`, или
- непустой `skill_set`, или
- непустой `experience`.

## Import через UI (dev/demo)

1. Войти в приложение.
2. Открыть `Settings` (`/settings`).
3. В секции HH import выбрать файл `hh_profile_sample.json` (или edge-case fixture).
4. При необходимости указать `resume_id` (например, `res-full`).
5. Нажать импорт fallback JSON.
6. Убедиться, что показан success c `resume_id` и списком обновлённых секций.

## Import через API / curl

Ниже минимальный reproducible пример:

```bash
curl -X POST "http://localhost:8000/api/v1/integrations/hh/import-json" \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  --data @- <<'JSON'
{
  "consent": true,
  "resume_id": "res-full",
  "payload": {
    "me": {"id": "user-1"},
    "resumes_mine": {"items": [{"id": "res-basic"}, {"id": "res-full"}]},
    "resumes": [
      {"id": "res-basic", "title": "Python Backend Engineer", "description": "..."},
      {"id": "res-full", "title": "Senior Python Engineer", "description": "...", "skill_set": ["Python"]}
    ]
  }
}
JSON
```

Для полноценных данных удобнее подставить fixture целиком (содержимое `hh_profile_sample.json`) в `payload`.

## Как выбирать `resume_id`

Рекомендация:

1. Сначала посмотреть `id` в `resumes_mine.items` (или `resumes[].id`).
2. Передать выбранный `resume_id` в body.
3. Если `resume_id` не передан — будет выбран первый «полезный» resume.
4. Если `resume_id` передан, но не найден — API вернёт `400 Resume not found in payload`.

## Поддерживаемые field variations

- salary: `amount` или `from/to`;
- dates в `experience.start/end`: `YYYY-MM-DD`, `YYYY-MM`, `YYYY` или dict `{year, month?, day?}`;
- `skill_set`: массив строк и/или объектов `{name}`;
- `language[].level`: string или `{name}`;
- `contact[]`: URL из `value` или `formatted`.

## Live HH import vs fallback import

- `POST /api/v1/integrations/hh/import` — live flow через OAuth + HH API.
- `POST /api/v1/integrations/hh/import-json` — fallback flow без live HH API, только локальный JSON payload.
- Оба потока используют одинаковую import policy: обновление main profile полей + controlled replace для `experiences/skills/languages/links`.

## Verification checklist (recommended)

- [ ] Login
- [ ] Open settings (`/settings`)
- [ ] Upload sample fixture (`hh_profile_sample.json`)
- [ ] Import profile
- [ ] Verify profile main fields (`full_name`, `title`, `summary_about`, `salary_min`, `location/city`)
- [ ] Verify experiences
- [ ] Verify skills
- [ ] Verify languages
- [ ] Verify links

