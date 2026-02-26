import logging
from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Any, Optional

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.models import SavedSearch, Vacancy, VacancyRequirement
from app.integrations.hh_client import HHClient
from app.services.requirements_extractor import extract_requirements_from_description
from app.utils.text_clean import strip_html

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class HHImportFilters:
    text: str
    area: Optional[str] = None
    schedule: Optional[str] = None
    experience: Optional[str] = None
    salary_from: Optional[int] = None
    salary_to: Optional[int] = None
    currency: Optional[str] = None
    per_page: int = 20
    pages_limit: int = 1
    include_details: bool = True
    extra_params: dict[str, str | int | bool | list[str | int] | None] | None = None


@dataclass(slots=True)
class HHImportResult:
    pages_processed: int = 0
    vacancies_seen: int = 0
    saved_count: int = 0
    updated_count: int = 0
    errors_count: int = 0
    stop_by_cutoff: bool = False


class HHImportService:
    """Imports vacancies from HH API and stores them in Postgres with UPSERT."""

    def __init__(self, db: Session, hh_client: HHClient) -> None:
        self.db = db
        self.hh_client = hh_client

    async def import_vacancies(
        self,
        filters: HHImportFilters,
        *,
        cutoff_published_at: Optional[datetime] = None,
        start_page: int = 0,
    ) -> HHImportResult:
        result = HHImportResult()

        logger.info(
            "HH import started | text=%s area=%s schedule=%s experience=%s salary_from=%s salary_to=%s currency=%s per_page=%s pages_limit=%s include_details=%s start_page=%s cutoff=%s",
            filters.text,
            filters.area,
            filters.schedule,
            filters.experience,
            filters.salary_from,
            filters.salary_to,
            filters.currency,
            filters.per_page,
            filters.pages_limit,
            filters.include_details,
            start_page,
            cutoff_published_at,
        )

        total_pages_from_api: Optional[int] = None

        for offset in range(filters.pages_limit):
            page = start_page + offset
            page_payload = await self.hh_client.search_vacancies(
                text=filters.text,
                area=filters.area,
                schedule=filters.schedule,
                experience=filters.experience,
                salary=filters.salary_from,
                currency=filters.currency,
                page=page,
                per_page=filters.per_page,
                extra_params=filters.extra_params,
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
            updated_on_page = 0
            errors_on_page = 0
            stop_by_cutoff = False
            page_embedding_ids: set[int] = set()
            html_log_count = 0

            for item in items:
                try:
                    published_at = self._parse_hh_datetime(item.get("published_at"))
                    if cutoff_published_at and published_at and published_at <= cutoff_published_at:
                        stop_by_cutoff = True
                        continue

                    details: Optional[dict[str, Any]] = None
                    if filters.include_details:
                        details = await self.hh_client.get_vacancy_details(str(item.get("id")))

                    values = self._map_to_vacancy_values(item, details)
                    clean_description = strip_html(values.get("description") or "")

                    if html_log_count < 3:
                        logger.debug(
                            "HH vacancy description lengths | external_id=%s html_len=%s clean_len=%s",
                            values["external_id"],
                            len(values.get("description") or ""),
                            len(clean_description),
                        )
                        html_log_count += 1

                    is_existing = self._vacancy_exists(values["source"], values["external_id"])
                    vacancy_id = self._upsert_vacancy(values)

                    self._replace_generated_requirements(vacancy_id, details, clean_description)

                    page_embedding_ids.add(vacancy_id)

                    result.vacancies_seen += 1
                    if is_existing:
                        result.updated_count += 1
                        updated_on_page += 1
                    else:
                        result.saved_count += 1
                        saved_on_page += 1
                except Exception:  # noqa: BLE001
                    logger.exception("Failed to process HH vacancy | external_id=%s", item.get("id"))
                    self.db.rollback()
                    result.errors_count += 1
                    errors_on_page += 1

            self.db.commit()

            for vacancy_id in page_embedding_ids:
                self._schedule_vacancy_embedding(vacancy_id)

            result.pages_processed += 1

            logger.info(
                "HH page committed | page=%s saved=%s updated=%s errors=%s stop_by_cutoff=%s cumulative_saved=%s cumulative_updated=%s cumulative_errors=%s",
                page + 1,
                saved_on_page,
                updated_on_page,
                errors_on_page,
                stop_by_cutoff,
                result.saved_count,
                result.updated_count,
                result.errors_count,
            )

            if stop_by_cutoff:
                result.stop_by_cutoff = True
                break

            if total_pages_from_api is not None and page + 1 >= total_pages_from_api:
                break

            await self.hh_client.polite_delay()

        logger.info(
            "HH import finished | pages_processed=%s vacancies_seen=%s saved=%s updated=%s errors=%s stop_by_cutoff=%s",
            result.pages_processed,
            result.vacancies_seen,
            result.saved_count,
            result.updated_count,
            result.errors_count,
            result.stop_by_cutoff,
        )
        return result

    async def sync_saved_search(self, saved_search: SavedSearch) -> HHImportResult:
        cutoff = saved_search.last_seen_published_at or saved_search.last_sync_at

        filters = HHImportFilters(
            text=saved_search.text,
            area=saved_search.area,
            schedule=saved_search.schedule,
            experience=saved_search.experience,
            salary_from=saved_search.salary_from,
            salary_to=saved_search.salary_to,
            currency=saved_search.currency,
            per_page=saved_search.per_page,
            pages_limit=saved_search.pages_limit,
            include_details=True,
            extra_params=saved_search.filters_json,
        )

        result = await self.import_vacancies(
            filters,
            cutoff_published_at=cutoff,
            start_page=saved_search.cursor_page,
        )

        saved_search.last_sync_at = datetime.now(timezone.utc)
        latest_seen = self._latest_published_at(fallback_cutoff=saved_search.last_seen_published_at)

        if latest_seen:
            saved_search.last_seen_published_at = latest_seen

        saved_search.cursor_page = 0 if result.stop_by_cutoff else saved_search.cursor_page + result.pages_processed
        self.db.add(saved_search)
        self.db.commit()
        self.db.refresh(saved_search)

        return result

    def _latest_published_at(self, *, fallback_cutoff: Optional[datetime]) -> Optional[datetime]:
        stmt = (
            select(Vacancy.published_at)
            .where(
                Vacancy.source == "hh",
                Vacancy.title.is_not(None),
            )
            .order_by(Vacancy.published_at.desc())
            .limit(1)
        )
        latest = self.db.execute(stmt).scalar_one_or_none()
        return latest or fallback_cutoff


    @staticmethod
    def _schedule_vacancy_embedding(vacancy_id: int) -> None:
        from app.tasks.embedding_tasks import build_vacancy_embedding

        build_vacancy_embedding.delay(vacancy_id)

    def _upsert_vacancy(self, values: dict[str, Any]) -> int:
        stmt = insert(Vacancy).values(**values)
        update_fields = {k: stmt.excluded[k] for k in values if k not in {"source", "external_id"}}

        stmt = stmt.on_conflict_do_update(
            constraint="uq_vacancies_source_external_id",
            set_=update_fields,
        )
        result = self.db.execute(stmt.returning(Vacancy.id))
        return int(result.scalar_one())

    def _replace_generated_requirements(
        self,
        vacancy_id: int,
        details: Optional[dict[str, Any]],
        clean_description: str,
    ) -> None:
        self.db.execute(
            delete(VacancyRequirement).where(
                VacancyRequirement.vacancy_id == vacancy_id,
                VacancyRequirement.kind.in_(("skill", "constraint")),
            )
        )

        requirements: list[VacancyRequirement] = []
        seen: set[tuple[str, str]] = set()

        generated_skill_requirements = self._build_skill_requirements(details, clean_description)
        for requirement in generated_skill_requirements:
            normalized = requirement["normalized_key"]
            dedupe_key = ("skill", normalized or requirement["raw_text"])
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            requirements.append(
                VacancyRequirement(
                    vacancy_id=vacancy_id,
                    kind="skill",
                    raw_text=requirement["raw_text"],
                    normalized_key=normalized,
                    weight=requirement["weight"],
                    is_hard=requirement["is_hard"],
                )
            )

        for raw_text, normalized_key, is_hard in self._extract_constraints(details, clean_description):
            dedupe_key = ("constraint", normalized_key)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            requirements.append(
                VacancyRequirement(
                    vacancy_id=vacancy_id,
                    kind="constraint",
                    raw_text=raw_text,
                    normalized_key=normalized_key,
                    weight=3 if is_hard else 1,
                    is_hard=is_hard,
                )
            )

        if requirements:
            self.db.add_all(requirements)

    @staticmethod
    def _extract_skills(details: Optional[dict[str, Any]]) -> list[str]:
        if not details:
            return []

        skills: list[str] = []
        for skill in details.get("key_skills") or []:
            name = (skill or {}).get("name")
            if isinstance(name, str):
                cleaned = name.strip()
                if cleaned:
                    skills.append(cleaned)
        return skills

    def _build_skill_requirements(
        self,
        details: Optional[dict[str, Any]],
        clean_description: str,
    ) -> list[dict[str, Any]]:
        skill_requirements: dict[str, dict[str, Any]] = {}

        for raw_skill in self._extract_skills(details):
            normalized = self._normalize_requirement_value(raw_skill)
            key = normalized or raw_skill
            skill_requirements[key] = {
                "raw_text": raw_skill,
                "normalized_key": normalized,
                "is_hard": False,
                "weight": 1,
            }

        for requirement in extract_requirements_from_description(clean_description):
            key = requirement["normalized_key"] or requirement["raw_text"]
            existing = skill_requirements.get(key)
            if existing is None or (requirement["is_hard"] and not existing["is_hard"]):
                skill_requirements[key] = {
                    "raw_text": requirement["raw_text"],
                    "normalized_key": requirement["normalized_key"],
                    "is_hard": requirement["is_hard"],
                    "weight": requirement["weight"],
                }

        return list(skill_requirements.values())

    @classmethod
    def _extract_constraints(
        cls,
        details: Optional[dict[str, Any]],
        clean_description: str,
    ) -> list[tuple[str, str, bool]]:
        if not details:
            return []

        constraints: list[tuple[str, str, bool]] = []
        hard_markers = ("обязательно", "необходимо", "требуется")
        normalized_description = cls._normalize_requirement_value(clean_description)
        has_hard_markers = any(marker in normalized_description for marker in hard_markers)
        mappings = {
            "experience": details.get("experience"),
            "schedule": details.get("schedule"),
            "employment": details.get("employment"),
            "area": details.get("area"),
        }

        for key, value in mappings.items():
            if not isinstance(value, dict):
                continue

            raw_value = value.get("id") or value.get("name")
            if not isinstance(raw_value, str) or not raw_value.strip():
                continue

            normalized_value = cls._normalize_requirement_value(raw_value)
            if not normalized_value:
                continue

            constraints.append((f"{key}: {raw_value}", f"{key}:{normalized_value}", has_hard_markers))

        return constraints

    @staticmethod
    def _normalize_requirement_value(value: str) -> str:
        lowered = value.lower()
        cleaned = re.sub(r"[^\w\s-]", " ", lowered, flags=re.UNICODE)
        squashed = " ".join(cleaned.split())
        return squashed

    def _vacancy_exists(self, source: str, external_id: str) -> bool:
        stmt = select(Vacancy.id).where(Vacancy.source == source, Vacancy.external_id == external_id).limit(1)
        return self.db.execute(stmt).scalar_one_or_none() is not None

    @staticmethod
    def _map_to_vacancy_values(item: dict[str, Any], details: Optional[dict[str, Any]]) -> dict[str, Any]:
        salary = item.get("salary") or {}
        snippet = item.get("snippet") or {}

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
            "published_at": HHImportService._parse_hh_datetime(item.get("published_at")),
            "status": "open",
        }

    @staticmethod
    def _parse_hh_datetime(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        return datetime.fromisoformat(value)
