from app.services.hh_browser_connect_service import HHBrowserAutomationError
from app.services.hh_browser_error_taxonomy import AutomationErrorCode, normalize_automation_error_code


def test_normalize_legacy_codes_to_stable_taxonomy() -> None:
    assert normalize_automation_error_code("HH_SELECTOR_NOT_FOUND") == AutomationErrorCode.SELECTOR_NOT_FOUND
    assert normalize_automation_error_code("ACTION_FAILED") == AutomationErrorCode.CONTROL_NOT_INTERACTABLE
    assert normalize_automation_error_code("UNRECOGNIZED_STATE") == AutomationErrorCode.PAGE_NOT_RECOGNIZED
    assert normalize_automation_error_code("SESSION_TIMEOUT") == "session_timeout"


def test_connect_service_automation_error_is_normalized() -> None:
    error = HHBrowserAutomationError("HH_SELECTOR_NOT_FOUND", "broken selector")
    assert error.code == AutomationErrorCode.SELECTOR_NOT_FOUND
