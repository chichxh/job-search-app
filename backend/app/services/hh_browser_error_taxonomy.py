from __future__ import annotations


class AutomationErrorCode:
    SELECTOR_NOT_FOUND = "selector_not_found"
    PAGE_NOT_RECOGNIZED = "page_not_recognized"
    UNEXPECTED_NAVIGATION = "unexpected_navigation"
    CONTROL_NOT_INTERACTABLE = "control_not_interactable"
    AUTH_STATE_UNKNOWN = "auth_state_unknown"
    APPLY_SURFACE_NOT_AVAILABLE = "apply_surface_not_available"
    RESUME_SURFACE_NOT_AVAILABLE = "resume_surface_not_available"


LEGACY_AUTOMATION_ERROR_ALIASES = {
    "HH_SELECTOR_NOT_FOUND": AutomationErrorCode.SELECTOR_NOT_FOUND,
    "ACTION_FAILED": AutomationErrorCode.CONTROL_NOT_INTERACTABLE,
    "UNRECOGNIZED_STATE": AutomationErrorCode.PAGE_NOT_RECOGNIZED,
    "TRANSIENT_NAVIGATION": "transient_navigation",
    "TRANSIENT_WAIT": "transient_wait",
    "NETWORK_ERROR": "network_error",
}


def normalize_automation_error_code(code: str) -> str:
    if code in LEGACY_AUTOMATION_ERROR_ALIASES:
        return LEGACY_AUTOMATION_ERROR_ALIASES[code]
    return code
