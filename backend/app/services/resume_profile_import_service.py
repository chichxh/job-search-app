from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import re
from typing import Any
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.db.models import Profile, ProfileExperience, ProfileLanguage, ProfileLink, ProfileSkill


class ResumeProfileParseError(Exception):
    """Raised when resume parsing cannot produce a usable draft."""


class ResumeProfileApplyError(Exception):
    """Raised when parsed draft cannot be applied to profile."""


@dataclass(slots=True)
class ResumeProfileDraft:
    full_name: str | None
    title: str | None
    location: str | None
    summary_about: str | None
    salary_min: int | None
    experiences: list[dict[str, Any]]
    skills: list[dict[str, Any]]
    languages: list[dict[str, Any]]
    links: list[dict[str, Any]]
    warnings: list[str]
    quality_hints: dict[str, Any]


class ResumeProfileParser:
    _SECTION_ALIASES: dict[str, set[str]] = {
        "summary": {"summary", "about", "profile", "objective", "о себе", "профиль", "summary/about"},
        "experience": {"experience", "work experience", "employment", "опыт", "опыт работы"},
        "skills": {"skills", "tech stack", "technologies", "навыки", "стек", "компетенции"},
        "languages": {"languages", "языки", "language"},
    }

    _MONTHS = {
        "jan": 1,
        "january": 1,
        "янв": 1,
        "январ": 1,
        "feb": 2,
        "february": 2,
        "фев": 2,
        "феврал": 2,
        "mar": 3,
        "march": 3,
        "мар": 3,
        "апр": 4,
        "apr": 4,
        "april": 4,
        "may": 5,
        "май": 5,
        "jun": 6,
        "june": 6,
        "июн": 6,
        "jul": 7,
        "july": 7,
        "июл": 7,
        "aug": 8,
        "august": 8,
        "авг": 8,
        "sep": 9,
        "sept": 9,
        "september": 9,
        "сен": 9,
        "oct": 10,
        "october": 10,
        "окт": 10,
        "nov": 11,
        "november": 11,
        "ноя": 11,
        "dec": 12,
        "december": 12,
        "дек": 12,
    }

    _ROLE_MARKERS = (
        "engineer",
        "developer",
        "manager",
        "lead",
        "qa",
        "analyst",
        "architect",
        "девелопер",
        "разработ",
        "инженер",
        "менеджер",
        "аналитик",
    )

    def parse(self, extracted_text: str) -> ResumeProfileDraft:
        normalized_text = self._normalize_text(extracted_text)
        if len(normalized_text) < 20:
            raise ResumeProfileParseError("Extracted text is too short to parse")

        lines = [line.strip() for line in normalized_text.split("\n") if line.strip()]
        sections = self._split_sections(lines)

        warnings: list[str] = []
        full_name = self._extract_full_name(lines)
        title = self._extract_title(lines, full_name)
        location = self._extract_location(lines)
        summary_about = self._extract_summary(sections)
        salary_min = self._extract_salary_min(normalized_text)

        skills = self._extract_skills(sections)
        languages = self._extract_languages(sections)
        links = self._extract_links(normalized_text)
        experiences = self._extract_experiences(sections)

        if not summary_about:
            warnings.append("Summary/about section not confidently extracted")
        if not experiences:
            warnings.append("No work experiences extracted")
        if not skills:
            warnings.append("No skills extracted")

        useful_main = sum(bool(item) for item in (full_name, title, summary_about, location, salary_min))
        useful_sections = sum(bool(section) for section in (experiences, skills, languages, links))
        useful_signal_score = useful_main + useful_sections

        if useful_signal_score == 0:
            raise ResumeProfileParseError("Nothing useful found in resume text")

        quality_hints = {
            "signal_counts": {
                "main_fields": useful_main,
                "experiences": len(experiences),
                "skills": len(skills),
                "languages": len(languages),
                "links": len(links),
            },
            "useful_signal_score": useful_signal_score,
            "confidence_label": "high" if useful_signal_score >= 6 else "medium" if useful_signal_score >= 3 else "low",
        }

        return ResumeProfileDraft(
            full_name=full_name,
            title=title,
            location=location,
            summary_about=summary_about,
            salary_min=salary_min,
            experiences=experiences,
            skills=skills,
            languages=languages,
            links=links,
            warnings=warnings,
            quality_hints=quality_hints,
        )

    @staticmethod
    def _normalize_text(text: str) -> str:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"[ \t]{2,}", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _split_sections(self, lines: list[str]) -> dict[str, list[str]]:
        sections: dict[str, list[str]] = {"header": []}
        current = "header"

        for line in lines:
            lowered = line.strip().lower().strip(":")
            matched = None
            for canonical, aliases in self._SECTION_ALIASES.items():
                if lowered in aliases:
                    matched = canonical
                    break
            if matched:
                current = matched
                sections.setdefault(current, [])
                continue
            sections.setdefault(current, []).append(line)

        return sections

    @staticmethod
    def _extract_full_name(lines: list[str]) -> str | None:
        for line in lines[:5]:
            if len(line.split()) not in {2, 3, 4}:
                continue
            if any(char.isdigit() for char in line):
                continue
            if "@" in line or "http" in line.lower():
                continue
            if line.lower().startswith(("summary", "about", "опыт", "skills", "навыки")):
                continue
            return line
        return None

    def _extract_title(self, lines: list[str], full_name: str | None) -> str | None:
        for line in lines[:8]:
            if full_name and line == full_name:
                continue
            lowered = line.lower()
            if any(marker in lowered for marker in self._ROLE_MARKERS):
                return line
        return None

    @staticmethod
    def _extract_location(lines: list[str]) -> str | None:
        for line in lines[:12]:
            lowered = line.lower()
            if lowered.startswith(("location:", "city:", "город:", "локация:")):
                return line.split(":", 1)[1].strip() or None
            if re.search(r"\b(remote|hybrid|moscow|saint petersburg|new york|berlin|london|санкт-петербург|москва)\b", lowered):
                return line
        return None

    def _extract_summary(self, sections: dict[str, list[str]]) -> str | None:
        summary_lines = sections.get("summary", [])
        if summary_lines:
            return "\n".join(summary_lines[:6]).strip() or None

        header_lines = sections.get("header", [])
        long_lines = [line for line in header_lines if len(line) > 80]
        if long_lines:
            return long_lines[0]
        return None

    @staticmethod
    def _extract_salary_min(text: str) -> int | None:
        salary_patterns = [
            r"(?:salary|compensation|desired salary|зарплата|ожидаемая зарплата)\D{0,20}(\d[\d\s]{3,})",
            r"(\d[\d\s]{3,})\s*(?:rub|usd|eur|₽|руб|\$)",
        ]
        for pattern in salary_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if not match:
                continue
            raw = re.sub(r"\D", "", match.group(1))
            if raw:
                value = int(raw)
                if value >= 10000:
                    return value
        return None

    def _extract_experiences(self, sections: dict[str, list[str]]) -> list[dict[str, Any]]:
        experience_lines = sections.get("experience", [])
        if not experience_lines:
            return []

        experiences: list[dict[str, Any]] = []
        current: dict[str, Any] | None = None

        for line in experience_lines:
            period = self._extract_period(line)
            if period:
                if current and current.get("start_date"):
                    experiences.append(current)
                current = {
                    "company_name": "Unknown company",
                    "position_title": "Unknown position",
                    "start_date": period[0],
                    "end_date": period[1],
                    "is_current": period[1] is None,
                    "description": "",
                }
                continue

            if current is None:
                continue

            if current["company_name"] == "Unknown company":
                current["company_name"] = line[:255]
                continue

            if current["position_title"] == "Unknown position":
                current["position_title"] = line[:255]
                continue

            if len(current["description"]) < 2000:
                current["description"] = (current["description"] + "\n" + line).strip()

        if current and current.get("start_date"):
            experiences.append(current)

        return experiences

    def _extract_period(self, line: str) -> tuple[date, date | None] | None:
        cleaned = line.replace("—", "-").replace("–", "-")
        parts = [part.strip() for part in cleaned.split("-") if part.strip()]
        if len(parts) < 2:
            return None

        start = self._parse_date(parts[0])
        if not start:
            return None

        end_part = parts[1].lower()
        if end_part in {"present", "current", "now", "настоящее время", "по настоящее время"}:
            return start, None

        end = self._parse_date(parts[1])
        return (start, end) if start else None

    def _parse_date(self, raw: str) -> date | None:
        value = raw.strip().lower()
        iso_match = re.match(r"^(\d{4})[-/.](\d{1,2})(?:[-/.](\d{1,2}))?$", value)
        if iso_match:
            year, month = int(iso_match.group(1)), int(iso_match.group(2))
            day = int(iso_match.group(3) or 1)
            try:
                return date(year, month, day)
            except ValueError:
                return None

        month_year = re.match(r"^([a-zа-яё]+)\s+(\d{4})$", value)
        if month_year:
            month_token, year_token = month_year.groups()
            month = self._month_from_token(month_token)
            if month:
                return date(int(year_token), month, 1)

        if value.isdigit() and len(value) == 4:
            return date(int(value), 1, 1)

        return None

    def _month_from_token(self, token: str) -> int | None:
        normalized = token.strip(".")
        for key, month in self._MONTHS.items():
            if normalized.startswith(key):
                return month
        return None

    def _extract_skills(self, sections: dict[str, list[str]]) -> list[dict[str, Any]]:
        skill_lines = sections.get("skills", [])
        skills_raw: list[str] = []

        for line in skill_lines:
            for part in re.split(r"[,;|•·]", line):
                clean = part.strip()
                if clean:
                    skills_raw.append(clean)

        deduped = self._dedupe_tokens(skills_raw)
        return [
            {
                "name_raw": skill,
                "normalized_key": self._normalize_skill_key(skill),
                "category": "hard_skill",
                "level": "intermediate",
            }
            for skill in deduped
        ]

    def _extract_languages(self, sections: dict[str, list[str]]) -> list[dict[str, str]]:
        language_lines = sections.get("languages", [])
        languages: list[dict[str, str]] = []
        for line in language_lines:
            chunks = [chunk.strip() for chunk in re.split(r"[-–—:]", line, maxsplit=1)]
            if not chunks or not chunks[0]:
                continue
            level = chunks[1] if len(chunks) > 1 and chunks[1] else "unknown"
            languages.append({"language": chunks[0], "level": level})
        return languages

    def _extract_links(self, text: str) -> list[dict[str, str | None]]:
        links: list[dict[str, str | None]] = []
        seen: set[str] = set()

        for email in re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text):
            if email.lower() in seen:
                continue
            seen.add(email.lower())
            links.append({"type": "email", "url": f"mailto:{email}", "label": "Email"})

        for raw_url in re.findall(r"(?:https?://|www\.)[^\s)>,]+", text):
            normalized = raw_url if raw_url.startswith("http") else f"https://{raw_url}"
            if normalized.lower() in seen:
                continue
            seen.add(normalized.lower())
            link_type = self._classify_link_type(normalized)
            links.append({"type": link_type, "url": normalized, "label": None})

        for telegram in re.findall(r"@([A-Za-z0-9_]{5,})", text):
            url = f"https://t.me/{telegram}"
            if url.lower() in seen:
                continue
            seen.add(url.lower())
            links.append({"type": "telegram", "url": url, "label": "Telegram"})

        return links

    @staticmethod
    def _classify_link_type(url: str) -> str:
        host = urlparse(url).netloc.lower()
        if "github.com" in host:
            return "github"
        if "linkedin.com" in host:
            return "linkedin"
        if "t.me" in host or "telegram.me" in host:
            return "telegram"
        return "website"

    @staticmethod
    def _normalize_skill_key(skill: str) -> str:
        return re.sub(r"\s+", " ", skill.strip().lower())

    @staticmethod
    def _dedupe_tokens(values: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for value in values:
            if not value or len(value) < 2:
                continue
            normalized = re.sub(r"\s+", " ", value).strip().lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(value.strip())
        return deduped


class ResumeProfileApplyService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def apply_draft(
        self,
        *,
        profile: Profile,
        draft: dict[str, Any],
        update_main_fields: bool,
        replace_sections: list[str],
    ) -> tuple[list[str], list[str], list[str]]:
        updated_fields: list[str] = []
        replaced_sections: list[str] = []
        warnings: list[str] = []

        if not self._has_useful_content(draft):
            raise ResumeProfileApplyError("Parsed draft has no useful content to import")

        if update_main_fields:
            updated_fields.extend(self._apply_main_fields(profile=profile, draft=draft))

        allowed_sections = {"experiences", "skills", "languages", "links"}
        invalid_sections = [name for name in replace_sections if name not in allowed_sections]
        if invalid_sections:
            raise ResumeProfileApplyError(f"Unsupported sections requested: {', '.join(sorted(invalid_sections))}")

        for section in replace_sections:
            if section == "experiences":
                self._replace_experiences(profile.id, draft.get("experiences") or [], warnings)
            elif section == "skills":
                self._replace_skills(profile.id, draft.get("skills") or [], warnings)
            elif section == "languages":
                self._replace_languages(profile.id, draft.get("languages") or [], warnings)
            elif section == "links":
                self._replace_links(profile.id, draft.get("links") or [], warnings)
            replaced_sections.append(section)

        self.db.add(profile)
        self.db.commit()
        return sorted(set(updated_fields)), replaced_sections, warnings

    @staticmethod
    def _has_useful_content(draft: dict[str, Any]) -> bool:
        if any(draft.get(field) for field in ("full_name", "title", "location", "summary_about", "salary_min")):
            return True
        for section in ("experiences", "skills", "languages", "links"):
            if draft.get(section):
                return True
        return False

    @staticmethod
    def _clean_text(value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        text = value.strip()
        return text or None

    def _apply_main_fields(self, *, profile: Profile, draft: dict[str, Any]) -> list[str]:
        updated: list[str] = []

        def apply(field: str, value: Any) -> None:
            if value is None:
                return
            setattr(profile, field, value)
            updated.append(field)

        apply("full_name", self._clean_text(draft.get("full_name")))
        apply("title", self._clean_text(draft.get("title")))
        location = self._clean_text(draft.get("location"))
        apply("location", location)
        apply("city", location)
        apply("summary_about", self._clean_text(draft.get("summary_about")))

        salary_min = draft.get("salary_min")
        if isinstance(salary_min, (int, float)) and salary_min > 0:
            apply("salary_min", int(salary_min))

        skills = draft.get("skills") or []
        skill_names = [self._clean_text(item.get("name_raw")) for item in skills if isinstance(item, dict)]
        normalized_skill_names = [name for name in skill_names if name]
        if normalized_skill_names:
            apply("skills_text", ", ".join(normalized_skill_names))

        return updated

    def _replace_experiences(self, profile_id: int, raw_experiences: list[dict[str, Any]], warnings: list[str]) -> None:
        self._delete_for_profile(ProfileExperience, profile_id)

        for raw in raw_experiences:
            if not isinstance(raw, dict):
                continue
            start_date = self._parse_partial_date(raw.get("start_date"))
            if not start_date:
                warnings.append("Skipped experience without valid start date")
                continue
            end_date = self._parse_partial_date(raw.get("end_date"))

            description = self._clean_text(raw.get("description")) or self._clean_text(raw.get("responsibilities_text"))
            self.db.add(
                ProfileExperience(
                    profile_id=profile_id,
                    company_name=self._clean_text(raw.get("company_name")) or "Unknown company",
                    position_title=self._clean_text(raw.get("position_title")) or "Unknown position",
                    location=self._clean_text(raw.get("location")),
                    start_date=start_date,
                    end_date=end_date,
                    is_current=bool(raw.get("is_current") or end_date is None),
                    responsibilities_text=description or "Imported from resume draft",
                    achievements_text=self._clean_text(raw.get("achievements_text")) or "",
                    tech_stack_text=self._clean_text(raw.get("tech_stack_text")),
                    employment_type=self._clean_text(raw.get("employment_type")),
                )
            )

    def _replace_skills(self, profile_id: int, raw_skills: list[dict[str, Any]], warnings: list[str]) -> None:
        self._delete_for_profile(ProfileSkill, profile_id)
        seen: set[str] = set()

        for raw in raw_skills:
            if not isinstance(raw, dict):
                continue
            name = self._clean_text(raw.get("name_raw"))
            if not name:
                continue
            normalized = self._clean_text(raw.get("normalized_key")) or name.lower()
            normalized = re.sub(r"\s+", " ", normalized)
            if normalized in seen:
                warnings.append(f"Skipped duplicate skill: {name}")
                continue
            seen.add(normalized)

            self.db.add(
                ProfileSkill(
                    profile_id=profile_id,
                    name_raw=name,
                    normalized_key=normalized,
                    category=self._clean_text(raw.get("category")) or "hard_skill",
                    level=self._clean_text(raw.get("level")) or "intermediate",
                    years=float(raw["years"]) if isinstance(raw.get("years"), (int, float)) else None,
                    last_used_year=int(raw["last_used_year"]) if isinstance(raw.get("last_used_year"), int) else None,
                    is_primary=bool(raw.get("is_primary", False)),
                    evidence_text=self._clean_text(raw.get("evidence_text")),
                )
            )

    def _replace_languages(self, profile_id: int, raw_languages: list[dict[str, Any]], _warnings: list[str]) -> None:
        self._delete_for_profile(ProfileLanguage, profile_id)
        for raw in raw_languages:
            if not isinstance(raw, dict):
                continue
            language = self._clean_text(raw.get("language"))
            if not language:
                continue
            level = self._clean_text(raw.get("level")) or "unknown"
            self.db.add(ProfileLanguage(profile_id=profile_id, language=language, level=level))

    def _replace_links(self, profile_id: int, raw_links: list[dict[str, Any]], _warnings: list[str]) -> None:
        self._delete_for_profile(ProfileLink, profile_id)
        seen: set[str] = set()
        for raw in raw_links:
            if not isinstance(raw, dict):
                continue
            url = self._clean_text(raw.get("url"))
            if not url or url.lower() in seen:
                continue
            seen.add(url.lower())
            self.db.add(
                ProfileLink(
                    profile_id=profile_id,
                    type=self._clean_text(raw.get("type")) or "other",
                    url=url,
                    label=self._clean_text(raw.get("label")),
                )
            )

    def _delete_for_profile(self, model: Any, profile_id: int) -> None:
        for item in [entry for entry in self.db.query(model).all() if entry.profile_id == profile_id]:
            self.db.delete(item)

    @staticmethod
    def _parse_partial_date(raw: Any) -> date | None:
        if isinstance(raw, date):
            return raw
        if not raw:
            return None
        if isinstance(raw, str):
            value = raw.strip()
            if re.match(r"^\d{4}-\d{2}-\d{2}$", value):
                year, month, day = [int(chunk) for chunk in value.split("-")]
                return date(year, month, day)
            if re.match(r"^\d{4}-\d{2}$", value):
                year, month = [int(chunk) for chunk in value.split("-")]
                return date(year, month, 1)
            if re.match(r"^\d{4}$", value):
                return date(int(value), 1, 1)
        return None
