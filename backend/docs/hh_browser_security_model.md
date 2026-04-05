# HH browser automation security model (MVP)

This document describes current security boundaries for the HH browser automation layer.

## What is persisted

- HH password is **never persisted** in DB, files, or logs.
- OTP / verification code is **never persisted** in DB, files, or logs.
- Persisted auth material is limited to browser storage state (cookies + origins) saved in controlled local storage.
- Database stores only a `session_state_ref` pointer, not raw storage JSON.

## Session storage controls

- Session state files are written only under a controlled `HH_BROWSER_SESSION_DIR` directory (default: `/tmp/job-search-app/hh_browser_sessions`).
- Session directory permission is hardened to `0700`; session file permission is hardened to `0600`.
- Session file names are opaque random IDs; they do not encode user email/phone/password.
- Disconnect and reauth cleanup paths delete session files physically.
- Corrupted/missing storage refs trigger safe cleanup and do not expose raw file paths in API responses.

## Logging and diagnostics policy

- Standard logs redact sensitive keys and values:
  - password / OTP
  - cookies and storage state payloads
  - tokens / auth blobs / session refs
  - full cover-letter and raw-resume text
  - email and phone values
- Debug summaries intentionally avoid DOM dumps, full HTML, and raw browser storage payloads.
- API-facing automation errors are short and safe (no stack traces, no raw browser data).

## Operational limitations (honest notes)

- Session state is stored on local filesystem, not in external KMS.
- At-rest encryption is delegated to host/container disk controls.
- Runtime browser memory still contains live credentials during active flow (by design), but these values are not persisted.
- If host-level filesystem access is compromised, local session files can be read until revoked/expired.
