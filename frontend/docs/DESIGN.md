# Frontend UI Guide (Final Polish)

## Visual principles
- **Product-first, not marketing:** интерфейс должен ускорять ежедневный workflow (вакансии → рекомендации → отклики).
- **Calm density:** компактные панели, мягкие бордеры, минимум визуального шума.
- **Action clarity:** у каждого критичного блока есть явный следующий шаг (primary action + hint).

## Base patterns
- **Page identity:** используйте `PageHeader` для единых eyebrow/title/subtitle на всех ключевых страницах.
- **Section container:** используйте `SectionCard` как базовую поверхность для данных, фильтров и action-зон.
- **Buttons:**
  - `.button` — primary.
  - `.button.button--secondary` — secondary.
  - `.button.button--danger` — destructive.
- **Status:**
  - `StatusPill` для inline-статусов процессов.
  - `VerdictBadge` для recommendation verdict.
  - `.error-banner`, `.success-banner`, `.loading`, `.empty-state` для сообщений состояния.

## Forms and states
- Единые стили `input/select/textarea` + читаемый `:focus-visible`.
- Disabled элементы должны визуально отличаться (`opacity + subdued background`) и не выглядеть интерактивными.
- Ошибки показывать рядом с действием в спокойном, но заметном стиле (через `ErrorBanner`).

## Spacing and typography
- Следовать токенам spacing из `index.css` (`--space-*`), не добавлять случайные margin/padding.
- Для карточек: `--space-3`/`--space-4` внутри, `--space-2`/`--space-3` между элементами.
- Иерархия заголовков:
  - page title ~1.6–1.9rem,
  - section title ~1rem,
  - мета/подсказки 0.75–0.9rem.

## Responsive rules
- На узких экранах панели и таблице-подобные ряды должны стекаться в 1 колонку.
- Toolbars и filter rows всегда `flex-wrap`, без горизонтального скролла.
- Auth layout переключается с двух колонок на одну, сохраняя читаемую форму выше промо-блока.

## Legacy cleanup rules
- Не возвращать старые utility-классы с конфликтующими цветами и отступами.
- Не смешивать несколько визуальных паттернов для одинаковых задач (например, разные типы кнопок в одной toolbar).
- Любой новый UI-элемент должен переиспользовать существующие токены/компоненты перед созданием нового стиля.
