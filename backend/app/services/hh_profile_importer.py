from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import Profile, ProfileExperience, ProfileLanguage, ProfileLink, ProfileSkill


class HHImportPayloadError(Exception):
    """Raised for normalized HH-like payload issues."""


@dataclass(slots=True)
class HHSelectedResume:
    resume_id: str
    resume_payload: dict[str, Any]


class HHProfileImporter:
    def __init__(self, db: Session) -> None:
        self.db = db

    def import_resume(self, *, profile: Profile, resume: dict[str, Any]) -> tuple[list[str], list[str]]:
        updated_fields = self._apply_profile_fields(profile, resume)
        replaced_sections = self._replace_profile_sections(profile.id, resume)
        return updated_fields, replaced_sections

    def select_resume_from_payload(self, *, payload: Any, resume_id: str | None) -> HHSelectedResume:
        if not isinstance(payload, dict):
            raise HHImportPayloadError("Invalid JSON shape: payload must be an object")

        candidates = self._collect_resume_candidates(payload)
        if not candidates:
            raise HHImportPayloadError("Unsupported payload format: resume data not found")

        if resume_id:
            for candidate in candidates:
                candidate_id = self._resume_identifier(candidate)
                if candidate_id and candidate_id == str(resume_id):
                    if not self._has_useful_resume_content(candidate):
                        raise HHImportPayloadError("Payload missing useful resume content")
                    return HHSelectedResume(resume_id=candidate_id, resume_payload=candidate)
            raise HHImportPayloadError("Resume not found in payload")

        for candidate in candidates:
            if self._has_useful_resume_content(candidate):
                return HHSelectedResume(
                    resume_id=self._resume_identifier(candidate) or "json-fallback",
                    resume_payload=candidate,
                )

        raise HHImportPayloadError("Payload missing useful resume content")

    def _apply_profile_fields(self, profile: Profile, resume: dict[str, Any]) -> list[str]:
        updated: list[str] = []

        def apply(field: str, value: Any) -> None:
            if value is None:
                return
            setattr(profile, field, value)
            updated.append(field)

        first_name = self._clean_text(resume.get("first_name"))
        last_name = self._clean_text(resume.get("last_name"))
        middle_name = self._clean_text(resume.get("middle_name"))
        full_name = " ".join(part for part in [last_name, first_name, middle_name] if part).strip()

        apply("full_name", full_name or None)
        apply("title", self._clean_text(resume.get("title")))

        summary_text = self._extract_summary_text(resume)
        if summary_text:
            apply("summary_about", summary_text)

        area = resume.get("area")
        area_name = area.get("name") if isinstance(area, dict) else self._clean_text(area)
        apply("location", area_name)
        apply("city", area_name)

        salary = resume.get("salary")
        salary_min = self._extract_salary_min(salary)
        if salary_min is not None:
            apply("salary_min", salary_min)

        relocation = resume.get("relocation") or {}
        if isinstance(relocation, dict):
            apply("relocation_ok", bool(relocation.get("type", "") not in {"no_relocation", "impossible"}))

        travel = resume.get("travel_time") or {}
        if isinstance(travel, dict):
            apply("remote_ok", travel.get("id") in {"none", "any"})

        skills = self._normalize_skill_names(resume.get("skill_set"))
        if skills:
            apply("skills_text", ", ".join(skills))

        description = self._clean_text(resume.get("description"))
        if description:
            apply("resume_text", description)

        return sorted(set(updated))

    def _replace_profile_sections(self, profile_id: int, resume: dict[str, Any]) -> list[str]:
        self._delete_for_profile(ProfileExperience, profile_id)
        self._delete_for_profile(ProfileSkill, profile_id)
        self._delete_for_profile(ProfileLanguage, profile_id)
        self._delete_for_profile(ProfileLink, profile_id)

        for exp in self._normalize_experiences(resume.get("experience")):
            start = self._parse_partial_date(exp.get("start"))
            if not start:
                continue
            end = self._parse_partial_date(exp.get("end"))
            area = exp.get("area")
            location = area.get("name") if isinstance(area, dict) else self._clean_text(area)

            self.db.add(
                ProfileExperience(
                    profile_id=profile_id,
                    company_name=self._clean_text(exp.get("company")) or "Unknown company",
                    position_title=self._clean_text(exp.get("position")) or "Unknown position",
                    location=location,
                    start_date=start,
                    end_date=end,
                    is_current=end is None,
                    responsibilities_text=self._clean_text(exp.get("description")) or "Imported from HH",
                    achievements_text="",
                    tech_stack_text=None,
                    employment_type=(exp.get("employment") or {}).get("name") if isinstance(exp.get("employment"), dict) else None,
                )
            )

        for skill_name in self._normalize_skill_names(resume.get("skill_set")):
            self.db.add(
                ProfileSkill(
                    profile_id=profile_id,
                    name_raw=skill_name,
                    normalized_key=skill_name.lower(),
                    category="hard_skill",
                    level="intermediate",
                    is_primary=False,
                )
            )

        for lang in self._normalize_languages(resume.get("language")):
            language_name = self._clean_text(lang.get("name"))
            if not language_name:
                continue
            level = "unknown"
            raw_level = lang.get("level")
            if isinstance(raw_level, dict):
                level = self._clean_text(raw_level.get("name")) or "unknown"
            elif isinstance(raw_level, str):
                level = self._clean_text(raw_level) or "unknown"

            self.db.add(
                ProfileLanguage(
                    profile_id=profile_id,
                    language=language_name,
                    level=level,
                )
            )

        for contact in self._normalize_contacts(resume.get("contact")):
            url = self._clean_text(contact.get("value")) or self._clean_text(contact.get("formatted"))
            if not url:
                continue
            link_type = (contact.get("type") or {}).get("id") if isinstance(contact.get("type"), dict) else "other"
            self.db.add(
                ProfileLink(
                    profile_id=profile_id,
                    type=link_type or "other",
                    url=url,
                    label=(contact.get("type") or {}).get("name") if isinstance(contact.get("type"), dict) else None,
                )
            )

        return ["experiences", "skills", "languages", "links"]

    @staticmethod
    def _clean_text(value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        cleaned = value.strip()
        return cleaned or None

    @staticmethod
    def _extract_salary_min(salary: Any) -> int | None:
        if not isinstance(salary, dict):
            return None

        def normalize_amount(raw: Any) -> int | None:
            if isinstance(raw, (int, float)):
                return int(raw)
            if isinstance(raw, str) and raw.strip().isdigit():
                return int(raw.strip())
            return None

        for key in ("amount", "from", "to"):
            parsed = normalize_amount(salary.get(key))
            if parsed is not None:
                return parsed
        return None

    def _extract_summary_text(self, resume: dict[str, Any]) -> str | None:
        for key in ("skills", "summary", "description"):
            text = self._clean_text(resume.get(key))
            if text:
                return text
        return None

    @staticmethod
    def _normalize_skill_names(skill_set: Any) -> list[str]:
        if not isinstance(skill_set, list):
            return []
        names: list[str] = []
        for raw in skill_set:
            if isinstance(raw, dict):
                name = raw.get("name")
            else:
                name = raw
            if isinstance(name, str) and name.strip():
                names.append(name.strip())
        return names

    @staticmethod
    def _normalize_experiences(raw_experience: Any) -> list[dict[str, Any]]:
        if not isinstance(raw_experience, list):
            return []
        return [item for item in raw_experience if isinstance(item, dict)]

    @staticmethod
    def _normalize_languages(raw_languages: Any) -> list[dict[str, Any]]:
        if not isinstance(raw_languages, list):
            return []
        normalized: list[dict[str, Any]] = []
        for item in raw_languages:
            if isinstance(item, dict):
                normalized.append(item)
            elif isinstance(item, str):
                normalized.append({"name": item})
        return normalized

    @staticmethod
    def _normalize_contacts(raw_contacts: Any) -> list[dict[str, Any]]:
        if not isinstance(raw_contacts, list):
            return []
        return [item for item in raw_contacts if isinstance(item, dict)]

    def _collect_resume_candidates(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []

        direct_resume = payload.get("resume")
        if isinstance(direct_resume, dict):
            candidates.append(direct_resume)

        raw_resumes = payload.get("resumes")
        if isinstance(raw_resumes, list):
            candidates.extend(item for item in raw_resumes if isinstance(item, dict))

        resumes_mine_items = ((payload.get("resumes_mine") or {}).get("items") if isinstance(payload.get("resumes_mine"), dict) else None)
        if isinstance(resumes_mine_items, list):
            candidates.extend(item for item in resumes_mine_items if isinstance(item, dict))

        if self._looks_like_resume(payload):
            candidates.append(payload)

        deduped: list[dict[str, Any]] = []
        seen_signatures: set[str] = set()
        for candidate in candidates:
            signature = str(candidate.get("id") or id(candidate))
            if signature in seen_signatures:
                continue
            deduped.append(candidate)
            seen_signatures.add(signature)
        return deduped

    @staticmethod
    def _looks_like_resume(raw: dict[str, Any]) -> bool:
        resume_keys = {"id", "title", "first_name", "last_name", "experience", "skill_set", "description", "contact"}
        return bool(resume_keys.intersection(raw.keys()))

    def _has_useful_resume_content(self, resume: dict[str, Any]) -> bool:
        if self._clean_text(resume.get("description")):
            return True
        if self._clean_text(resume.get("title")):
            return True
        if self._clean_text(resume.get("skills")):
            return True
        if self._normalize_skill_names(resume.get("skill_set")):
            return True
        if self._normalize_experiences(resume.get("experience")):
            return True
        return False

    @staticmethod
    def _resume_identifier(resume: dict[str, Any]) -> str | None:
        raw_id = resume.get("id")
        if raw_id is None:
            return None
        return str(raw_id)

    def _delete_for_profile(self, model: Any, profile_id: int) -> None:
        for item in [entry for entry in self.db.query(model).all() if entry.profile_id == profile_id]:
            self.db.delete(item)

    @staticmethod
    def _parse_partial_date(raw: Any) -> date | None:
        if isinstance(raw, str):
            chunks = raw.split("-")
            if len(chunks) == 3:
                try:
                    return date(int(chunks[0]), int(chunks[1]), int(chunks[2]))
                except ValueError:
                    return None
            if len(chunks) == 2:
                try:
                    return date(int(chunks[0]), int(chunks[1]), 1)
                except ValueError:
                    return None
            if len(chunks) == 1 and chunks[0].isdigit():
                return date(int(chunks[0]), 1, 1)
            return None

        if not isinstance(raw, dict):
            return None

        year = raw.get("year")
        month = raw.get("month") or 1
        day = raw.get("day") or 1
        if not year:
            return None
        try:
            return date(int(year), int(month), int(day))
        except ValueError:
            return None
