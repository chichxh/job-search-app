# HH targeted resume visibility policy (privacy-first)

## Default backend policy

For every newly created HH managed targeted resume, backend policy is explicit and privacy-first:

- `auto_hide_from_all_enabled=true` by default.
- This means intended visibility is `hidden_from_all`.
- Creation flow records desired/current visibility states in `hh_managed_resumes` and triggers (or marks pending) hide-from-all enforcement.

## Explicit user opt-out

Creation request supports explicit override:

- `do_not_hide_from_all_employers=true`

When enabled:

- backend sets `auto_hide_from_all_enabled=false`
- backend does **not** force hide-from-all
- desired/current visibility policy is persisted as explicit opt-out (`public_default` intent)

## Apply flow policy

Before apply:

- if `auto_hide_from_all_enabled=true`, backend enforces hidden visibility (`hidden_from_all`) and attempts hide-from-all when needed.
- if `auto_hide_from_all_enabled=false`, backend does not force hide-from-all.

After successful apply with auto-hide policy enabled:

- backend stores inferred HH transition as `current_visibility_mode=visible_selected_employers`
- `visibility_status=inferred_post_apply` marks that this state is HH-side inferred behavior and may later be replaced by active read-back checks.

## Why this is the safe default

HH behavior allows applying while resume is hidden and may auto-transition visibility after submit.

A backend-enforced default of hide-from-all minimizes accidental resume exposure while still preserving ability to apply. Explicit opt-out remains available for users who intentionally prefer broader visibility.
