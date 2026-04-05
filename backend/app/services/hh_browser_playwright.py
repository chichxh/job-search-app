from __future__ import annotations

import os
from typing import Literal

from app.services.hh_browser_connect_service import HHBrowserAutomationError, HHLoginPageAdapter, HHLoginStep


class PlaywrightHHLoginAdapter(HHLoginPageAdapter):
    def __init__(self) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:  # noqa: BLE001
            raise HHBrowserAutomationError("PLAYWRIGHT_UNAVAILABLE", "Playwright is not installed") from exc

        self._sync_playwright = sync_playwright
        self._pw = self._sync_playwright().start()
        headless = os.getenv("HH_PLAYWRIGHT_HEADLESS", "true").lower() != "false"
        self._browser = self._pw.chromium.launch(headless=headless)
        self._context = self._browser.new_context()
        self._page = self._context.new_page()

    def open_login_page(self) -> HHLoginStep:
        self._page.goto("https://hh.ru/account/login", wait_until="domcontentloaded", timeout=30_000)
        return self._detect_step()

    def submit_identifier(self, *, identifier: str, identifier_type: Literal["phone", "email"]) -> HHLoginStep:
        input_selectors = [
            "input[type='tel']",
            "input[type='email']",
            "input[name*='login']",
            "input[name*='username']",
            "input[data-qa*='login']",
        ]
        if identifier_type == "phone":
            input_selectors = ["input[type='tel']"] + input_selectors
        else:
            input_selectors = ["input[type='email']"] + input_selectors

        self._fill_first(input_selectors, identifier)
        self._click_first([
            "button:has-text('Дальше')",
            "button[type='submit']",
            "button[data-qa*='submit']",
        ])
        self._page.wait_for_timeout(700)
        return self._detect_step()

    def submit_password(self, *, password: str) -> HHLoginStep:
        self._fill_first([
            "input[type='password']",
            "input[name*='password']",
            "input[data-qa*='password']",
        ], password)
        self._click_first([
            "button:has-text('Войти')",
            "button[type='submit']",
            "button[data-qa*='submit']",
        ])
        self._page.wait_for_timeout(700)
        return self._detect_step()

    def submit_code(self, *, code: str) -> HHLoginStep:
        self._fill_first([
            "input[inputmode='numeric']",
            "input[name*='otp']",
            "input[name*='code']",
            "input[data-qa*='code']",
        ], code)
        self._click_first([
            "button:has-text('Подтвердить')",
            "button:has-text('Войти')",
            "button[type='submit']",
        ])
        self._page.wait_for_timeout(700)
        return self._detect_step()

    def export_storage_state(self) -> dict:
        return self._context.storage_state()

    def close(self) -> None:
        try:
            self._context.close()
            self._browser.close()
            self._pw.stop()
        except Exception:  # noqa: BLE001
            return

    def _detect_step(self) -> HHLoginStep:
        if self._looks_authenticated():
            return "connected"

        if self._matches_any(["input[type='password']", "input[name*='password']"]):
            return "awaiting_password"

        if self._matches_any(["input[name*='otp']", "input[name*='code']", "input[inputmode='numeric']"]):
            return "awaiting_code"

        if self._matches_any(["input[type='tel']", "input[type='email']", "button:has-text('Дальше')"]):
            return "awaiting_identifier"

        if self._matches_any(["text=Войти с паролем"]):
            self._click_first(["button:has-text('Войти с паролем')", "text=Войти с паролем"])
            self._page.wait_for_timeout(500)
            if self._matches_any(["input[type='password']"]):
                return "awaiting_password"

        return "failed"

    def _looks_authenticated(self) -> bool:
        url = self._page.url
        if "/applicant" in url or "/resume" in url:
            return True
        return self._matches_any(["[data-qa='mainmenu_applicantProfile']", "a[href*='/applicant']"])

    def _matches_any(self, selectors: list[str]) -> bool:
        for selector in selectors:
            locator = self._page.locator(selector)
            if locator.count() > 0 and locator.first.is_visible():
                return True
        return False

    def _fill_first(self, selectors: list[str], value: str) -> None:
        for selector in selectors:
            locator = self._page.locator(selector)
            if locator.count() > 0:
                locator.first.fill(value)
                return
        raise HHBrowserAutomationError("HH_SELECTOR_NOT_FOUND", "Unable to find expected input on HH login page")

    def _click_first(self, selectors: list[str]) -> None:
        for selector in selectors:
            locator = self._page.locator(selector)
            if locator.count() > 0:
                locator.first.click()
                return
        raise HHBrowserAutomationError("HH_SELECTOR_NOT_FOUND", "Unable to find expected action button on HH login page")


class PlaywrightAdapterFactory:
    def create(self) -> HHLoginPageAdapter:
        return PlaywrightHHLoginAdapter()
