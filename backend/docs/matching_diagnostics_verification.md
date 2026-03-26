# Matching quality diagnostics & reproducible verification

Цель: получать измеримый сигнал качества parsing+matching без ручного SQL.

## 1) Backfill parsed vacancies

```bash
curl -sS -X POST \
  "http://127.0.0.1:8000/api/v1/dev/vacancies/hh/backfill-parsed?limit=200&only_missing=false&schedule_embeddings=false&schedule_recommendations=false"
```

Сохраните `task_id`, затем дождитесь `SUCCESS`:

```bash
curl -sS "http://127.0.0.1:8000/api/v1/tasks/<task_id>"
```

## 2) Rebuild embeddings

```bash
# vacancy embeddings
curl -sS -X POST "http://127.0.0.1:8000/api/v1/dev/embeddings/rebuild-vacancies?limit=200"

# profile embeddings
curl -sS -X POST "http://127.0.0.1:8000/api/v1/dev/embeddings/rebuild-profiles?limit=20"
```

## 3) Recompute recommendations

```bash
curl -sS -X POST \
  "http://127.0.0.1:8000/api/v1/profiles/<profile_id>/recommendations/recompute?limit=50"
```

Проверьте статус recompute через `/api/v1/tasks/<task_id>`.

## 4) Global diagnostics snapshot

```bash
curl -sS "http://127.0.0.1:8000/dev/matching/diagnostics?low_quality_threshold=0.45"
```

Поля:
- `total_vacancies`
- `vacancies_with_vacancy_parsed`
- `vacancies_with_requirements_lines_gt_0`
- `vacancies_with_skill_requirements_gt_0`
- `vacancies_with_hard_requirements_gt_0`
- `low_quality_vacancies_count`

## 5) Profile diagnostics snapshot

```bash
# profile-only summary
curl -sS "http://127.0.0.1:8000/dev/profiles/<profile_id>/matching/diagnostics?top_n=10"

# combined global + profile summary
curl -sS "http://127.0.0.1:8000/dev/matching/diagnostics?profile_id=<profile_id>&top_n=10"
```

Поля:
- `recommendations_count`
- `verdict_distribution`
- `recommendations_with_evidence_gt_0`
- `top_recommendations[]`:
  - `vacancy_id`, `title`, `final_score`, `verdict`
  - `semantic_component`, `hard_coverage`, `nice_coverage`
  - `key_warnings`, `key_penalties`, `quality_caps`

## 6) Что смотреть после improvements

Минимальный quality checklist:

1. Растёт доля `vacancies_with_requirements_lines_gt_0 / vacancies_with_vacancy_parsed`.
2. Растёт доля `vacancies_with_skill_requirements_gt_0 / total_vacancies`.
3. Растёт доля `vacancies_with_hard_requirements_gt_0 / total_vacancies`.
4. Падает `low_quality_vacancies_count`.
5. Для целевого профиля растёт `recommendations_with_evidence_gt_0 / recommendations_count`.
6. В `top_recommendations` меньше записей с `quality_caps` (`quality_score<...`, `skill_requirements_count==0` и т.п.).
7. `verdict_distribution` сдвигается из `weak/reject` в `ok/strong` без роста “ложных strong” (ручной spot-check 3-5 вакансий).

## 7) Рекомендуемый ручной цикл проверки

1. Зафиксировать baseline (global + profile diagnostics JSON).
2. Внести изменения в parsing/matching.
3. Прогнать шаги 1–3.
4. Снять новый diagnostics snapshot.
5. Сравнить baseline vs new по чек-листу из раздела 6.
