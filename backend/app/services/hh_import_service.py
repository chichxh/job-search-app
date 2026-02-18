import logging
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.models import Vacancy
from app.integrations.hh_client import HHClient

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class HHImportFilters:
    text: str
    area: Optional[str] = None
    per_page: int = 20
    pages_limit: int = 1
    include_details: bool = True


@dataclass(slots=True)
class HHImportResult:
    pages_processed: int = 0
    vacancies_seen: int = 0
    vacancies_saved: int = 0


class HHImportService:
    """Imports vacancies from HH API and stores them in Postgres with UPSERT."""

    def __init__(self, db: Session, hh_client: HHClient) -> None:
        self.db = db
        self.hh_client = hh_client

    async def import_vacancies(self, filters: HHImportFilters) -> HHImportResult:
        result = HHImportResult()

        logger.info(
            "HH import started | text=%s area=%s per_page=%s pages_limit=%s",
            filters.text,
            filters.area,
            filters.per_page,
            filters.pages_limit,
        )

        total_pages_from_api: Optional[int] = None

        for page in range(filters.pages_limit):
            page_payload = await self.hh_client.search_vacancies(
                text=filters.text,
                area=filters.area,
                page=page,
                per_page=filters.per_page,
            )

            total_pages_from_api = page_payload.get("pages", total_pages_from_api)
            items: list[dict[str, Any]] = page_payload.get("items", [])

            logger.info(
                "HH page processed | page=%s/%s items=%s found=%s",
                page + 1,
                total_pages_from_api,
                len(items),
                page_payload.get("found"),
            )

            saved_on_page = 0
            for item in items:
                details: Optional[dict[str, Any]] = None
                if filters.include_details:
                    details = await self.hh_client.get_vacancy_details(str(item.get("id")))

                values = self._map_to_vacancy_values(item, details)
                self._upsert_vacancy(values)
                result.vacancies_seen += 1
                result.vacancies_saved += 1
                saved_on_page += 1

            self.db.commit()
            result.pages_processed += 1

            logger.info(
                "HH page committed | page=%s saved=%s cumulative_saved=%s",
                page + 1,
                saved_on_page,
                result.vacancies_saved,
            )

            if total_pages_from_api is not None and page + 1 >= total_pages_from_api:
                break

            await self.hh_client.polite_delay()

        logger.info(
            "HH import finished | pages_processed=%s vacancies_seen=%s vacancies_saved=%s",
            result.pages_processed,
            result.vacancies_seen,
            result.vacancies_saved,
        )
        return result

    def _upsert_vacancy(self, values: dict[str, Any]) -> None:
        stmt = insert(Vacancy).values(**values)
        update_fields = {k: stmt.excluded[k] for k in values if k not in {"source", "external_id"}}

        stmt = stmt.on_conflict_do_update(
            constraint="uq_vacancies_source_external_id",
            set_=update_fields,
        )
        self.db.execute(stmt)

    @staticmethod
    def _map_to_vacancy_values(item: dict[str, Any], details: Optional[dict[str, Any]]) -> dict[str, Any]:
        salary = item.get("salary") or {}
        snippet = item.get("snippet") or {}
        description = None

        if details and details.get("description"):
            description = details["description"]
        else:
            parts = [snippet.get("requirement"), snippet.get("responsibility")]
            description = "\n\n".join(part for part in parts if part)

        return {
            "source": "hh",
            "external_id": str(item.get("id")),
            "title": item.get("name") or "",
            "company_name": (item.get("employer") or {}).get("name"),
            "location": (item.get("area") or {}).get("name"),
            "salary_from": salary.get("from"),
            "salary_to": salary.get("to"),
            "currency": salary.get("currency"),
            "description": description,
            "url": item.get("alternate_url"),
            "status": "open",
        }
