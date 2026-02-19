import asyncio
import os
import random
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Optional

import httpx


class HHAPIError(Exception):
    """Raised when HH API request fails after retries."""


class HHClient:
    """Async client for the official HeadHunter API."""

    BASE_URL = "https://api.hh.ru"

    def __init__(
        self,
        user_agent: Optional[str] = None,
        timeout: float = 10.0,
        max_retries: int = 5,
        min_delay_s: float = 0.2,
        max_delay_s: float = 0.5,
    ) -> None:
        self.user_agent = user_agent or os.getenv("HH_USER_AGENT")
        if not self.user_agent:
            raise ValueError("HH_USER_AGENT environment variable is required")

        self.timeout = timeout
        self.max_retries = max_retries
        self.min_delay_s = min_delay_s
        self.max_delay_s = max_delay_s
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "HHClient":
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=httpx.Timeout(self.timeout),
            headers={
                "User-Agent": self.user_agent,
                "Accept": "application/json",
            },
        )
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def search_vacancies(
        self,
        *,
        text: str,
        area: Optional[str] = None,
        schedule: Optional[str] = None,
        experience: Optional[str] = None,
        salary: Optional[int] = None,
        currency: Optional[str] = None,
        page: int = 0,
        per_page: int = 20,
        clusters: bool = False,
        extra_params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"text": text, "page": page, "per_page": per_page}
        if area:
            params["area"] = area
        if schedule:
            params["schedule"] = schedule
        if experience:
            params["experience"] = experience
        if salary is not None:
            params["salary"] = salary
        if currency:
            params["currency"] = currency
        if clusters:
            params["clusters"] = "true"

        return await self._request(
            "GET",
            "/vacancies",
            params=self._build_query_params(params, extra_params),
        )

    async def get_vacancy_clusters(
        self,
        *,
        text: str,
        area: Optional[str] = None,
        schedule: Optional[str] = None,
        experience: Optional[str] = None,
        salary: Optional[int] = None,
        currency: Optional[str] = None,
        extra_params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self.search_vacancies(
            text=text,
            area=area,
            schedule=schedule,
            experience=experience,
            salary=salary,
            currency=currency,
            page=0,
            per_page=1,
            clusters=True,
            extra_params=extra_params,
        )

    async def get_vacancy_details(self, vacancy_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/vacancies/{vacancy_id}")

    async def polite_delay(self) -> None:
        await asyncio.sleep(random.uniform(self.min_delay_s, self.max_delay_s))

    def _build_query_params(
        self,
        base_params: dict[str, Any],
        extra_params: dict[str, Any] | None,
    ) -> list[tuple[str, str]]:
        params: list[tuple[str, str]] = []

        for key, value in base_params.items():
            params.append((key, str(value)))

        if not extra_params:
            return params

        for key, value in extra_params.items():
            if value is None:
                continue
            if isinstance(value, list):
                for item in value:
                    params.append((key, str(item)))
                continue
            params.append((key, str(value)))

        return params

    async def _request(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        if not self._client:
            raise RuntimeError("HHClient must be used via 'async with HHClient(...)'")

        for attempt in range(self.max_retries):
            response = await self._client.request(method, url, **kwargs)

            if response.status_code < 400:
                return response.json()

            if response.status_code == 429:
                wait_s = self._extract_retry_after(response) or (2**attempt)
                if attempt == self.max_retries - 1:
                    break
                await asyncio.sleep(wait_s)
                continue

            if 500 <= response.status_code <= 599:
                if attempt == self.max_retries - 1:
                    break
                await asyncio.sleep(2**attempt)
                continue

            raise HHAPIError(
                f"HH API returned {response.status_code} for {method} {url}: {response.text[:300]}"
            )

        raise HHAPIError(f"HH API request failed after retries: {method} {url}")

    @staticmethod
    def _extract_retry_after(response: httpx.Response) -> Optional[float]:
        retry_after = response.headers.get("Retry-After")
        if not retry_after:
            return None

        if retry_after.isdigit():
            return float(retry_after)

        try:
            dt = parsedate_to_datetime(retry_after)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            wait_s = (dt - datetime.now(timezone.utc)).total_seconds()
            return max(wait_s, 0.0)
        except (TypeError, ValueError, IndexError):
            return None
