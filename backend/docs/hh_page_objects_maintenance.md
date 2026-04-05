# HH page objects / selectors maintenance layer (step: diagnostics hardening)

Этот документ фиксирует maintenance-архитектуру automation surface для HH, без добавления новых user-facing флоу.

## 1) Architecture overview

- **Page objects**: `HHLoginFlowPageModel` и `HHNavigationHelper` инкапсулируют login + applicant/resumes/vacancy/apply surfaces и дают единый API для orchestration.  
- **Selector registry**: `DEFAULT_SELECTORS` — единый источник правды для первичных и fallback локаторов (primary-first ordering), чтобы hot-fix делать в одном месте.  
- **Diagnostics layer**:
  - `diagnostics_report()` для login step surface;
  - `readiness_report()` по page object;
  - `selector_health_summary()` и `detect_current_page()` для быстрой инспекции «что сломалось».  
- **Error taxonomy**: централизована в `hh_browser_error_taxonomy.py`, с нормализацией legacy кодов в стабильные snake_case коды.

## 2) Нормализованные automation error codes

Базовые коды для поддержки/debugging:

- `selector_not_found`
- `page_not_recognized`
- `unexpected_navigation`
- `control_not_interactable`
- `auth_state_unknown`
- `apply_surface_not_available`
- `resume_surface_not_available`

Legacy-коды автоматически маппятся в новую таксономию через `normalize_automation_error_code`.

## 3) Selector strategy (primary vs fallback)

Принципы:

1. Для каждого control selectors идут в порядке: **primary -> fallback**.
2. Почему selector важен, документируется рядом с registry entry (комментарии рядом с группой).
3. Page objects не копируют локаторы вручную — используют только `SelectorRegistry`.
4. Любой hot-fix selector breakage выполняется через один registry entry, без каскадных правок по flow-коду.

## 4) Dev-safe debugging hooks

Доступны инструменты:

- structured readiness/health reports (без raw HTML dump);
- optional screenshot-on-failure (`HH_AUTOMATION_SCREENSHOT_DIR`) через `maybe_capture_screenshot_on_failure`;
- selector fallback usage и missing required controls в каждом readiness report.

Ограничения безопасности:

- без raw cookies/session dump в diagnostics;
- без логирования секретов (пароли, OTP, storage blob).

## 5) Troubleshooting guide

### A) HH login page изменилась

Симптомы:
- `page_not_recognized` или `selector_not_found` на login шагах.

Что делать:
1. Проверить `diagnostics_report()` и `current_detected_step`.
2. Посмотреть `selector_health.identifier_*`/`password`/`code`: что matched и где fallback.
3. Исправить только соответствующий блок в `DEFAULT_SELECTORS.login`.
4. Прогнать тесты page objects + connect service.

### B) Не находится apply surface

Симптомы:
- `apply_surface_not_available` после клика отклика.

Что делать:
1. Проверить `vacancy.readiness_report()` и `apply_surface.readiness_report()`.
2. Проверить, что `apply_entry` кликается и какие `surface_markers`/`resume_selector` отсутствуют.
3. Обновить `DEFAULT_SELECTORS.apply_surface` (primary/fallback), не трогая orchestration.

### C) Как понять, какой page object сломался

Быстрый путь:
1. Вызвать `detect_current_page()` — если `unknown`, вероятно сломан required marker текущего экрана.
2. Вызвать `selector_health_summary()`:
   - page с `missing_required_controls != []` — кандидат на поломку;
   - `fallback_selectors_used` показывает деградацию до запасных локаторов.
3. Фиксить selectors в соответствующей group секции registry.

## 6) Что НЕ входит в этот шаг

- targeted resume creation flow;
- visibility automation;
- apply submit flow;
- sync to applications.
