# Vacancy parsing backfill verification note

После изменений в extraction/normalization выполните короткий backfill и проверку:

1. Перепарсить вакансии и пересоздать requirements:

```bash
curl -X POST "http://localhost:8000/api/v1/dev/vacancies/hh/backfill-parsed?limit=200&only_missing=false"
```

2. Проверить, что requirements секция не пустая у заметной доли вакансий:

```sql
SELECT
  count(*) FILTER (
    WHERE jsonb_array_length(coalesce(sections_json->'requirements'->'lines','[]'::jsonb)) > 0
  ) AS with_requirements,
  count(*) AS total
FROM vacancy_parsed;
```

3. Проверить tricky токены и алиасы на нескольких вакансиях (ручной spot-check):
- C++, C#, Node.js, ASP.NET
- Docker Compose, Kubernetes/K8s
- GitHub Actions и GitLab CI

4. Проверить, что в `vacancy_requirements` нет ложного `Git` при наличии только `GitHub Actions`:

```sql
SELECT v.id, v.title, array_agg(r.raw_text ORDER BY r.raw_text)
FROM vacancies v
JOIN vacancy_requirements r ON r.vacancy_id = v.id
WHERE r.kind = 'skill'
  AND (
    r.raw_text IN ('Git', 'GitHub Actions')
    OR r.normalized_key IN ('git', 'github actions')
  )
GROUP BY v.id, v.title
ORDER BY v.id DESC
LIMIT 20;
```
