from __future__ import annotations

import os
from typing import Any, Literal

from app.services.hh_browser_connect_service import HHBrowserAutomationError, HHLoginPageAdapter, HHLoginStep, HHSessionProbeAdapter
from app.services.hh_browser_page_objects import HHLoginFlowPageModel, NormalizedAutomationError, to_legacy_step


class PlaywrightBrowserRuntime:
    def __init__(self, *, storage_state: dict | None = None) -> None:
        try:
            from playwright.sync_api import Error, TimeoutError, sync_playwright
        except Exception as exc:  # noqa: BLE001
            raise HHBrowserAutomationError("PLAYWRIGHT_UNAVAILABLE", "Playwright is not installed") from exc

        self.playwright_error = Error
        self.playwright_timeout_error = TimeoutError
        self._pw = sync_playwright().start()
        headless = os.getenv("HH_PLAYWRIGHT_HEADLESS", "true").lower() != "false"
        self._browser = self._pw.chromium.launch(headless=headless)
        self._context = self._browser.new_context(storage_state=storage_state) if storage_state else self._browser.new_context()
        self.page = self._context.new_page()

    def export_storage_state(self) -> dict:
        return self._context.storage_state()

    def close(self) -> None:
        try:
            self._context.close()
            self._browser.close()
            self._pw.stop()
        except Exception:  # noqa: BLE001
            return


class PlaywrightHHLoginAdapter(HHLoginPageAdapter):
    def __init__(self) -> None:
        self._runtime = PlaywrightBrowserRuntime()
        self._navigation_timeout_ms = int(os.getenv("HH_LOGIN_NAV_TIMEOUT_MS", "30000"))
        self._step_wait_timeout_ms = int(os.getenv("HH_LOGIN_STEP_TIMEOUT_MS", "12000"))
        self._flow = HHLoginFlowPageModel(page=self._runtime.page)

    def open_login_page(self) -> HHLoginStep:
        try:
            self._runtime.page.goto(
                "https://hh.ru/account/login",
                wait_until="domcontentloaded",
                timeout=self._navigation_timeout_ms,
            )
            return self._wait_step_detected()
        except self._runtime.playwright_timeout_error as exc:
            raise HHBrowserAutomationError("TRANSIENT_NAVIGATION", "Timed out while opening HH login page") from exc
        except self._runtime.playwright_error as exc:
            raise HHBrowserAutomationError("TRANSIENT_NAVIGATION", "Navigation to HH login page failed") from exc

    def submit_identifier(self, *, identifier: str, identifier_type: Literal["phone", "email"]) -> HHLoginStep:
        try:
            self._flow.fill_identifier(identifier=identifier, identifier_type=identifier_type)
            self._flow.submit_identifier()
            return self._wait_step_detected()
        except NormalizedAutomationError as exc:
            raise HHBrowserAutomationError(exc.code, exc.message, debug_summary=exc.debug_summary) from exc

    def submit_password(self, *, password: str) -> HHLoginStep:
        try:
            self._flow.fill_password(password=password)
            self._flow.submit_password()
            return self._wait_step_detected()
        except NormalizedAutomationError as exc:
            raise HHBrowserAutomationError(exc.code, exc.message, debug_summary=exc.debug_summary) from exc

    def submit_code(self, *, code: str) -> HHLoginStep:
        try:
            self._flow.fill_code(code=code)
            self._flow.submit_code()
            return self._wait_step_detected()
        except NormalizedAutomationError as exc:
            raise HHBrowserAutomationError(exc.code, exc.message, debug_summary=exc.debug_summary) from exc

    def export_storage_state(self) -> dict:
        return self._runtime.export_storage_state()

    def safe_debug_summary(self) -> dict[str, Any]:
        return self._flow.safe_summary()

    def close(self) -> None:
        self._runtime.close()

    def _wait_step_detected(self) -> HHLoginStep:
        try:
            self._runtime.page.wait_for_timeout(500)
            elapsed = 0
            while elapsed <= self._step_wait_timeout_ms:
                step = to_legacy_step(self._flow.detect_step().step_code)
                if step != "failed":
                    return step
                self._runtime.page.wait_for_timeout(250)
                elapsed += 250
            return "failed"
        except NormalizedAutomationError as exc:
            raise HHBrowserAutomationError(exc.code, exc.message, debug_summary=exc.debug_summary) from exc
        except self._runtime.playwright_timeout_error as exc:
            raise HHBrowserAutomationError("TRANSIENT_WAIT", "Timed out while waiting for HH step transition") from exc
        except self._runtime.playwright_error as exc:
            raise HHBrowserAutomationError("TRANSIENT_WAIT", "Failed while waiting for HH step transition") from exc


class PlaywrightAdapterFactory:
    def create(self) -> HHLoginPageAdapter:
        return PlaywrightHHLoginAdapter()


class PlaywrightHHSessionProbe(HHSessionProbeAdapter):
    def __init__(self, *, storage_state: dict) -> None:
        self._runtime = PlaywrightBrowserRuntime(storage_state=storage_state)
        self._flow = HHLoginFlowPageModel(page=self._runtime.page)
        self._timeout_ms = int(os.getenv("HH_LOGIN_NAV_TIMEOUT_MS", "30000"))

    def check_authenticated(self) -> bool:
        try:
            self._runtime.page.goto("https://hh.ru/applicant/resumes", wait_until="domcontentloaded", timeout=self._timeout_ms)
            return self._flow.detect_step().step_code == "authenticated"
        except self._runtime.playwright_timeout_error as exc:
            raise HHBrowserAutomationError("TRANSIENT_NAVIGATION", "Timed out while checking HH session") from exc
        except self._runtime.playwright_error as exc:
            raise HHBrowserAutomationError("TRANSIENT_NAVIGATION", "Failed while checking HH session") from exc

    def close(self) -> None:
        self._runtime.close()


class PlaywrightSessionProbeFactory:
    def create(self, *, storage_state: dict) -> HHSessionProbeAdapter:
        return PlaywrightHHSessionProbe(storage_state=storage_state)
