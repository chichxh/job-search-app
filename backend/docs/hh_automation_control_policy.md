# HH automation control policy (audit/security/ops)

This document defines the practical control layer around high-risk HH browser automation actions:

- `connect`
- `create_targeted_resume`
- `hide_visibility` (`visibility/hide-from-all`)
- `apply`

## 1. Audit trail model

All controlled actions write audit records to `hh_automation_action_runs`.

Audit fields:

- `action_type`
- `triggered_by`
- `target_type`, `target_id`, `target_ref`
- `request_fingerprint`
- `started_at`, `finished_at`
- `status`
- `operation_code`
- `safe_summary`
- `retry_of_action_id` / `parent_action_id`
- `context_ref` (safe references only, no sensitive payloads)

Operational statuses used by policy:

- `running`
- `completed`
- `retryable_failed`
- `failed` (terminal)
- `duplicate_prevented`
- `retry_skipped`
- `conflict_detected`
- `rate_limited`
- `cancelled`

## 2. Idempotency rules

### 2.1 Apply to vacancy

Fingerprint: `apply:{user_id}:{vacancy_id}:{hh_resume_managed_id}`.

Policy:

- If a completed action with same fingerprint already exists, duplicate request is prevented (`duplicate_prevented`) and previous `hh_apply_run` is reused.
- If previous action failed with terminal status, retry is blocked (`retry_skipped`).
- `retryable_failed` can be retried and links via `retry_of_action_id`.

### 2.2 Create targeted resume

Fingerprint: `create_targeted_resume:{user}:{profile}:{vacancy}:{source_resume_version}:{target_title}`.

Policy:

- Repeated completed request is prevented (`duplicate_prevented`) and previous managed resume is reused.
- Retry semantics match apply: retryable failures may be retried; terminal failures are blocked.

### 2.3 Visibility hide-from-all

Fingerprint: `hide_visibility:{user}:{managed_resume_id}:hidden_from_all`.

Policy:

- If resume is already `hidden_from_all` with `visibility_status=updated`, side effect is skipped and action is marked completed with `HH_DUPLICATE_PREVENTED`.
- Duplicate completed request is prevented by fingerprint policy.

## 3. Retry discipline

Retry behavior is explicit and deterministic:

- `retryable_failed` => retry is allowed and linked via `retry_of_action_id`.
- `failed` => retry is skipped with `HH_RETRY_SKIPPED_TERMINAL`.
- `duplicate_prevented` => no side effects, previous successful outcome reused.

## 4. Conflict / safety rails

### 4.1 Concurrent conflict guard

A new request is rejected with `HH_ACTION_CONFLICT_DETECTED` when the same `action_type + target_type + target_id` is already `running`.

Examples:

- no two concurrent applies on the same managed resume target
- no concurrent visibility hide actions for the same managed resume
- no overlapping connect flow starts for same user lifecycle state

### 4.2 Manual cancel rail

- Connect cancel (`/connect/cancel`) now records explicit `cancelled` action entry (`HH_ACTION_CANCELLED`).
- Generic action model supports `cancel_requested` for future asynchronous checkpoints.

## 5. Lightweight rate limiting / throttling

Application-level safeguards:

- Per-user max active controlled actions (`max_concurrent_per_user`) to cap parallel browser side effects.
- Short anti-spam interval (`min_interval_seconds`) on same fingerprint to prevent rapid button spam/retry storms.
- Violations produce explicit operation codes:
  - `HH_ACTION_RATE_LIMITED`
  - `HH_ACTION_SPAM_PREVENTED`

## 6. Logging / operational codes

`safe_summary` and `operation_code` are intended for operational debugging without secrets.

Key operation codes added:

- `HH_DUPLICATE_PREVENTED`
- `HH_RETRY_SKIPPED_TERMINAL`
- `HH_ACTION_CANCELLED`
- `HH_ACTION_CONFLICT_DETECTED`
- `HH_ACTION_RATE_LIMITED`
- `HH_ACTION_SPAM_PREVENTED`

No sensitive raw payloads or credentials are stored in audit summaries.

## 7. Error code normalization contract

Automation-facing error codes are persisted in canonical `snake_case` form across connection/session, targeted resume, visibility, and apply flows.

- Legacy uppercase aliases from older adapters are normalized at service boundaries.
- API responses and diagnostics should expose the normalized safe code only (for example, `transient_wait`, `page_not_recognized`, `session_expired`).
- `last_error_message` / `result_message` remain short user-facing summaries and must not include low-level traces or secret material.
