from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Literal

from app.services.hh_browser_connect_service import (
    HHBrowserAutomationError,
    HHLoginPageAdapter,
    HHLoginStep,
    HHSessionProbeAdapter,
)


@dataclass(frozen=True)
class HHLoginHeuristics:
    identifier_labels: tuple[str, ...] = ("Телефон", "Почта", "Телефон или почта")
    continue_texts: tuple[str, ...] = ("Дальше", "Продолжить")
    password_labels: tuple[str, ...] = ("Пароль",)
    password_entry_texts: tuple[str, ...] = ("Войти с паролем",)
    otp_labels: tuple[str, ...] = ("Код", "Код из SMS", "Код подтверждения")
    otp_entry_texts: tuple[str, ...] = ("Войти с помощью",)
    submit_texts: tuple[str, ...] = ("Войти", "Подтвердить", "Продолжить")


class PlaywrightHHLoginAdapter(HHLoginPageAdapter):
    def __init__(self) -> None:
        try:
            from playwright.sync_api import Error, TimeoutError, sync_playwright
        except Exception as exc:  # noqa: BLE001
            raise HHBrowserAutomationError("PLAYWRIGHT_UNAVAILABLE", "Playwright is not installed") from exc

        self._playwright_error = Error
        self._playwright_timeout_error = TimeoutError
        self._sync_playwright = sync_playwright
        self._pw = self._sync_playwright().start()
        headless = os.getenv("HH_PLAYWRIGHT_HEADLESS", "true").lower() != "false"
        self._browser = self._pw.chromium.launch(headless=headless)
        self._context = self._browser.new_context()
        self._page = self._context.new_page()
        self._heuristics = HHLoginHeuristics()
        self._navigation_timeout_ms = int(os.getenv("HH_LOGIN_NAV_TIMEOUT_MS", "30000"))
        self._step_wait_timeout_ms = int(os.getenv("HH_LOGIN_STEP_TIMEOUT_MS", "12000"))

    def open_login_page(self) -> HHLoginStep:
        try:
            self._page.goto("https://hh.ru/account/login", wait_until="domcontentloaded", timeout=self._navigation_timeout_ms)
            return self._wait_step_detected()
        except self._playwright_timeout_error as exc:
            raise HHBrowserAutomationError("TRANSIENT_NAVIGATION", "Timed out while opening HH login page") from exc
        except self._playwright_error as exc:
            raise HHBrowserAutomationError("TRANSIENT_NAVIGATION", "Navigation to HH login page failed") from exc

    def submit_identifier(self, *, identifier: str, identifier_type: Literal["phone", "email"]) -> HHLoginStep:
        self._fill_identifier(identifier=identifier, identifier_type=identifier_type)
        self._click_continue()
        return self._wait_step_detected()

    def submit_password(self, *, password: str) -> HHLoginStep:
        password_input = self._locate_password_input()
        if password_input is None:
            raise HHBrowserAutomationError("HH_SELECTOR_NOT_FOUND", "Unable to find HH password input", debug_summary=self.safe_debug_summary())
        password_input.fill(password)
        self._click_submit()
        return self._wait_step_detected()

    def submit_code(self, *, code: str) -> HHLoginStep:
        code_input = self._locate_code_input()
        if code_input is None:
            raise HHBrowserAutomationError("HH_SELECTOR_NOT_FOUND", "Unable to find HH OTP code input", debug_summary=self.safe_debug_summary())
        code_input.fill(code)
        self._click_submit()
        return self._wait_step_detected()

    def export_storage_state(self) -> dict:
        return self._context.storage_state()

    def safe_debug_summary(self) -> dict[str, Any]:
        return {
            "url": self._page.url,
            "title": self._page.title(),
            "has_password_input": self._locate_password_input() is not None,
            "has_code_input": self._locate_code_input() is not None,
            "has_identifier_input": self._locate_identifier_input("email") is not None
            or self._locate_identifier_input("phone") is not None,
        }

    def close(self) -> None:
        try:
            self._context.close()
            self._browser.close()
            self._pw.stop()
        except Exception:  # noqa: BLE001
            return

    def _wait_step_detected(self) -> HHLoginStep:
        try:
            self._page.wait_for_timeout(500)
            deadline = self._step_wait_timeout_ms
            elapsed = 0
            while elapsed <= deadline:
                step = self._detect_step()
                if step != "failed":
                    return step
                self._page.wait_for_timeout(250)
                elapsed += 250
            return "failed"
        except self._playwright_timeout_error as exc:
            raise HHBrowserAutomationError("TRANSIENT_WAIT", "Timed out while waiting for HH step transition") from exc
        except self._playwright_error as exc:
            raise HHBrowserAutomationError("TRANSIENT_WAIT", "Failed while waiting for HH step transition") from exc

    def _detect_step(self) -> HHLoginStep:
        if self._looks_authenticated():
            return "connected"

        if self._locate_password_input() is not None:
            return "awaiting_password"

        if self._locate_code_input() is not None:
            return "awaiting_code"

        if self._locate_identifier_input("email") is not None or self._locate_identifier_input("phone") is not None:
            return "awaiting_identifier"

        for text in self._heuristics.password_entry_texts:
            password_switch = self._page.get_by_role("button", name=text)
            if password_switch.count() > 0:
                password_switch.first.click()
                self._page.wait_for_timeout(350)
                if self._locate_password_input() is not None:
                    return "awaiting_password"

        return "failed"

    def _looks_authenticated(self) -> bool:
        url = self._page.url
        if "/applicant" in url or "/resume" in url:
            return True
        return self._page.locator("[data-qa='mainmenu_applicantProfile'],a[href*='/applicant']").count() > 0

    def _fill_identifier(self, *, identifier: str, identifier_type: Literal["phone", "email"]) -> None:
        input_locator = self._locate_identifier_input(identifier_type)
        if input_locator is None:
            raise HHBrowserAutomationError(
                "HH_SELECTOR_NOT_FOUND",
                "Unable to find HH identifier input",
                debug_summary=self.safe_debug_summary(),
            )
        input_locator.fill(identifier)

    def _click_continue(self) -> None:
        for text in self._heuristics.continue_texts:
            locator = self._page.get_by_role("button", name=text)
            if locator.count() > 0:
                locator.first.click()
                return
        submit = self._page.get_by_role("button", name="Дальше")
        if submit.count() > 0:
            submit.first.click()
            return
        self._click_submit()

    def _click_submit(self) -> None:
        for text in self._heuristics.submit_texts:
            locator = self._page.get_by_role("button", name=text)
            if locator.count() > 0:
                locator.first.click()
                return

        submit = self._page.locator("button[type='submit']")
        if submit.count() > 0:
            submit.first.click()
            return

        raise HHBrowserAutomationError(
            "HH_SELECTOR_NOT_FOUND",
            "Unable to find HH action button",
            debug_summary=self.safe_debug_summary(),
        )

    def _locate_identifier_input(self, identifier_type: Literal["phone", "email"]):
        labels = self._heuristics.identifier_labels
        preferred_labels = ("Телефон",) if identifier_type == "phone" else ("Почта",)
        for label in preferred_labels + labels:
            locator = self._page.get_by_label(label)
            if locator.count() > 0:
                return locator.first

        fallback_selectors = [
            "input[type='tel']",
            "input[type='email']",
            "input[name*='login']",
            "input[name*='username']",
            "input[data-qa*='login']",
        ]
        for selector in fallback_selectors:
            locator = self._page.locator(selector)
            if locator.count() > 0:
                return locator.first
        return None

    def _locate_password_input(self):
        for label in self._heuristics.password_labels:
            locator = self._page.get_by_label(label)
            if locator.count() > 0:
                return locator.first

        fallback = self._page.locator("input[type='password'],input[name*='password'],input[data-qa*='password']")
        if fallback.count() > 0:
            return fallback.first
        return None

    def _locate_code_input(self):
        for label in self._heuristics.otp_labels:
            locator = self._page.get_by_label(label)
            if locator.count() > 0:
                return locator.first

        fallback = self._page.locator("input[inputmode='numeric'],input[name*='otp'],input[name*='code'],input[data-qa*='code']")
        if fallback.count() > 0:
            return fallback.first
        return None


class PlaywrightAdapterFactory:
    def create(self) -> HHLoginPageAdapter:
        return PlaywrightHHLoginAdapter()


class PlaywrightHHSessionProbe(HHSessionProbeAdapter):
    def __init__(self, *, storage_state: dict) -> None:
        try:
            from playwright.sync_api import Error, TimeoutError, sync_playwright
        except Exception as exc:  # noqa: BLE001
            raise HHBrowserAutomationError("PLAYWRIGHT_UNAVAILABLE", "Playwright is not installed") from exc

        self._playwright_error = Error
        self._playwright_timeout_error = TimeoutError
        self._sync_playwright = sync_playwright
        self._pw = self._sync_playwright().start()
        headless = os.getenv("HH_PLAYWRIGHT_HEADLESS", "true").lower() != "false"
        self._browser = self._pw.chromium.launch(headless=headless)
        self._context = self._browser.new_context(storage_state=storage_state)
        self._page = self._context.new_page()
        self._timeout_ms = int(os.getenv("HH_LOGIN_NAV_TIMEOUT_MS", "30000"))

    def check_authenticated(self) -> bool:
        try:
            self._page.goto("https://hh.ru/applicant/resumes", wait_until="domcontentloaded", timeout=self._timeout_ms)
            if "/applicant" in self._page.url or "/resume" in self._page.url:
                return True
            return self._page.locator("[data-qa='mainmenu_applicantProfile'],a[href*='/applicant']").count() > 0
        except self._playwright_timeout_error as exc:
            raise HHBrowserAutomationError("TRANSIENT_NAVIGATION", "Timed out while checking HH session") from exc
        except self._playwright_error as exc:
            raise HHBrowserAutomationError("TRANSIENT_NAVIGATION", "Failed while checking HH session") from exc

    def close(self) -> None:
        try:
            self._context.close()
            self._browser.close()
            self._pw.stop()
        except Exception:  # noqa: BLE001
            return


class PlaywrightSessionProbeFactory:
    def create(self, *, storage_state: dict) -> HHSessionProbeAdapter:
        return PlaywrightHHSessionProbe(storage_state=storage_state)
