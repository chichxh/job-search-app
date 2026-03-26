# Matching calibration note (developer-oriented)

Этот этап не добавляет ML training pipeline, но делает текущий scoring калибруемым локально.

## Что теперь можно подстраивать

Базовые параметры вынесены в `MatchingScoringConfig` в `app/services/matching/matching_service.py`:

- `weights`:
  - `semantic`
  - `hard_coverage`
  - `nice_coverage`
- `verdict_thresholds`:
  - `strong_min`
  - `ok_min`
  - `weak_min`
- `penalties`:
  - `overqualified_multiplier`
  - `salary_warning_multiplier`
- `salary_rules`:
  - `hard_mismatch_ratio`
  - `severe_from_ratio`
- `quality_guard`:
  - `low_threshold`
  - `very_low_threshold`
  - `low_cap`
  - `very_low_cap`
  - `sparse_requirements_cap`
  - `min_reliable_skill_requirements`
- `experience_rules`:
  - `fail_tolerance_years`
  - `warning_tolerance_years`

## Offline utility

Добавлен скрипт: `backend/scripts/matching_calibration.py`.

Он позволяет:

- прогнать список `profile_id`/`vacancy_id` пар;
- увидеть для каждой пары:
  - `final_score`
  - `verdict`
  - `components` (semantic/hard/nice)
  - penalties и warnings;
- сравнить baseline и несколько вариантов параметров (`--variant label=path.json`);
- посчитать `precision@k`, если у пар есть `label` (`1`/`0`);
- проверить sanity по UX: сколько `reject` попало в top-k.

### Пример формата gold set

```json
[
  { "profile_id": 1, "vacancy_id": 10, "label": 1 },
  { "profile_id": 1, "vacancy_id": 11, "label": 0 },
  { "profile_id": 2, "vacancy_id": 14, "label": 1 }
]
```

### Пример варианта параметров

```json
{
  "weights": {
    "semantic": 0.50,
    "hard_coverage": 0.35,
    "nice_coverage": 0.15
  },
  "verdict_thresholds": {
    "strong_min": 0.78,
    "ok_min": 0.52,
    "weak_min": 0.32
  }
}
```

### Запуск

```bash
cd backend
python scripts/matching_calibration.py --pairs-json ./gold_pairs.json --top-k 5
python scripts/matching_calibration.py --pairs-json ./gold_pairs.json --variant tuned=./tuned_weights.json --top-k 5
```

## Как собирать маленький gold set вручную

- Возьмите 20–50 пар из реальных/демо профилей и вакансий.
- Для каждой пары проставьте бинарную метку релевантности (`label: 1/0`) по текущему продуктному смыслу.
- Включайте «спорные» пары (high semantic + missing hard skills), чтобы ловить деградации.

## Как оценивать sanity и не ломать UX

- Смотрите `precision@k` (обычно k=3/5/10).
- Проверяйте `reject_in_top_k`: для продового UX это должно стремиться к 0.
- Проверяйте распределение verdict: после тюнинга не должно быть резкого перекоса в `strong` или `reject`.
- Смотрите penalties/caps в объяснении: рост `no_skill_requirements_cap` обычно сигнал о проблемах parsing, а не о плохих кандидатах.

## Ограничения текущего подхода

- Это rule-based скоринг без статистической калибровки/обучения.
- Сравнение вариантов пока делается локально скриптом, без автоматического pipeline.
- Скрипт использует текущий `compute_for_pair` и обновляет `vacancy_scores` (подходит для dev/staging, не для online A/B).
