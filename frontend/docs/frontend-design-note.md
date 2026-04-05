# Frontend Design Note — Foundation Refresh

## Intent
Build a coherent product shell for a daily job-search workflow (not a marketing landing), with better hierarchy, consistency, and data readability.

## Visual principles
- **Linear influence:** compact density, calm typography, subtle borders, strong focus states.
- **Catawiki influence:** polished cards, breathing room, premium composition.
- **Ashby influence:** product-first navigation and data-heavy panels (boards, toolbars, utility surfaces).

## Foundation decisions
- Introduced a tokenized base layer in `index.css` for:
  - neutral/accent/status color system
  - spacing scale
  - radius scale
  - shadows
- Consolidated shared component patterns in `App.css`:
  - buttons (primary/secondary/small)
  - form controls (inputs/textareas/selects)
  - banners (info/success/error/loading/empty)
  - cards and status badges
  - toolbars and page header pattern

## App shell
- Replaced the previous top-only nav with a product shell:
  - persistent sidebar navigation
  - contextual topbar with page title/subtitle
  - account and quick sign-out controls
  - responsive fallback for narrower screens

## Scope in this PR
- Foundation-first implementation (tokens + shell + common patterns).
- Light adaptation of selected pages:
  - `VacanciesPage`
  - `RecommendationsPage`
- Existing business logic and backend API contracts are unchanged.

## Baseline patterns for future pages
- `page-header` for page identity.
- `toolbar` / `toolbar--subtle` for controls.
- unified `.button` variants.
- shared banners for loading/error/success/empty states.
- dense card/list surfaces for board and recommendation contexts.

## HH session lifecycle UX (Settings)
- HH browser integration card now surfaces compact session health metadata: connection status, session present/missing, `last_authenticated_at`, `last_checked_at`, and `requires_reauth`.
- The UI shows safe, user-facing session diagnostics (no storage refs, tokens, or debug payloads).
- Primary lifecycle actions:
  - **Проверить сессию** — explicit session health re-check.
  - **Переподключить HH** — shown when state indicates `requires_reauth` / failed flow.
  - **Отключить HH** — clear disconnect path.
  - **Восстановить сессию** — optional action in disconnected state when no session is currently attached.
- Guidance is stateful:
  - connected → calm confirmation that session is active;
  - requires_reauth → clear next step to reconnect;
  - transient check failures → retry guidance without treating it as logout;
  - disconnected → direct path to connect flow.
