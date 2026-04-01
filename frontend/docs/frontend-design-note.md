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
