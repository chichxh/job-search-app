from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import (
    HHBrowserConnection,
    HHManagedResume,
    Profile,
    ProfileEducation,
    ProfileExperience,
    ProfileLanguage,
    ProfileLink,
    ProfileSkill,
    ResumeVersion,
    Vacancy,
)
from app.schemas.hh_browser_integration import HHCreateTargetedResumeRequest, HHTargetedResumePayload
from app.services.hh_action_control_service import HHActionControlService


class HHResumeAutomationError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(slots=True)
class HHCreateResumeResult:
    external_id: str
    resume_url: str | None
    title: str


class HHResumeAutomationClient(Protocol):
    def create_targeted_resume(
        self,
        *,
        user_id: int,
        connection: HHBrowserConnection,
        payload: HHTargetedResumePayload,
        dry_run: bool,
    ) -> HHCreateResumeResult: ...


class HHResumeAutomationClientStub:
    def create_targeted_resume(
        self,
        *,
        user_id: int,
        connection: HHBrowserConnection,
        payload: HHTargetedResumePayload,
        dry_run: bool,
    ) -> HHCreateResumeResult:
        raise HHResumeAutomationError(
            code="AUTOMATION_NOT_IMPLEMENTED",
            message="HH resume constructor automation is not implemented in this build",
        )


class HHTargetedPayloadBuilder:
    def __init__(self, db: Session) -> None:
        self.db = db

    def build(
        self,
        *,
        profile: Profile,
        vacancy: Vacancy | None,
        source_resume_version: ResumeVersion | None,
        request: HHCreateTargetedResumeRequest,
    ) -> HHTargetedResumePayload:
        educations = self._profile_rows(ProfileEducation, profile.id)
        experiences = self._profile_rows(ProfileExperience, profile.id)
        skills = self._profile_rows(ProfileSkill, profile.id)
        languages = self._profile_rows(ProfileLanguage, profile.id)
        links = self._profile_rows(ProfileLink, profile.id)

        profession_title = (
            request.target_title
            or (vacancy.title if vacancy and vacancy.title else None)
            or profile.title
            or "Специалист"
        )

        chosen_skills = self._select_skills(skills=skills, focus=request.skills_focus)
        summary = self._build_summary(
            profile=profile,
            vacancy=vacancy,
            selected_skills=chosen_skills,
            source_resume_version=source_resume_version,
            summary_override=request.summary,
        )

        skill_level_hints = {item: self._skill_level_for_name(skills, item) for item in chosen_skills} if request.include_skill_levels else {}
        education_entries = [
            {
                "institution": e.institution,
                "degree_level": e.degree_level,
                "field_of_study": e.field_of_study,
                "start_year": e.start_year,
                "end_year": e.end_year,
            }
            for e in educations
        ]

        work_experience = [
            {
                "company_name": exp.company_name,
                "position_title": exp.position_title,
                "start_date": exp.start_date.isoformat() if exp.start_date else None,
                "end_date": exp.end_date.isoformat() if exp.end_date else None,
                "is_current": exp.is_current,
                "responsibilities_text": exp.responsibilities_text,
                "achievements_text": exp.achievements_text,
                "tech_stack_text": exp.tech_stack_text,
            }
            for exp in self._sort_experiences(experiences)[: request.max_experiences]
        ]

        emphasis = self._build_emphasis(vacancy=vacancy, selected_skills=chosen_skills, languages=languages, links=links)

        return HHTargetedResumePayload(
            profession_title=profession_title,
            summary=summary,
            education=education_entries,
            skills=chosen_skills,
            skill_level_hints=skill_level_hints,
            work_experience=work_experience,
            targeted_emphasis=emphasis,
        )

    def _profile_rows(self, model: Any, profile_id: int) -> list[Any]:
        return [item for item in self.db.query(model).all() if item.profile_id == profile_id]

    def _sort_experiences(self, experiences: list[ProfileExperience]) -> list[ProfileExperience]:
        return sorted(
            experiences,
            key=lambda item: (item.is_current, item.end_date or item.start_date),
            reverse=True,
        )

    def _select_skills(self, *, skills: list[ProfileSkill], focus: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []

        for focus_item in focus:
            normalized = focus_item.strip()
            if not normalized:
                continue
            key = normalized.casefold()
            if key not in seen:
                result.append(normalized)
                seen.add(key)

        primary_skills = sorted(skills, key=lambda item: (item.is_primary, item.years or 0), reverse=True)
        for skill in primary_skills:
            candidate = skill.name_raw.strip()
            if not candidate:
                continue
            key = candidate.casefold()
            if key in seen:
                continue
            result.append(candidate)
            seen.add(key)
            if len(result) >= 20:
                break

        return result

    def _skill_level_for_name(self, skills: list[ProfileSkill], skill_name: str) -> str:
        for item in skills:
            if item.name_raw.casefold() == skill_name.casefold():
                return item.level
        return ""

    def _build_summary(
        self,
        *,
        profile: Profile,
        vacancy: Vacancy | None,
        selected_skills: list[str],
        source_resume_version: ResumeVersion | None,
        summary_override: str | None,
    ) -> str:
        if summary_override:
            return summary_override.strip()

        source_chunks = [
            profile.summary_about or "",
            source_resume_version.content_text if source_resume_version else "",
            profile.resume_text,
        ]
        base_summary = next((chunk.strip() for chunk in source_chunks if chunk and chunk.strip()), "")

        vacancy_part = f"Фокус на вакансию: {vacancy.title}." if vacancy and vacancy.title else ""
        skills_part = f"Ключевые навыки: {', '.join(selected_skills[:8])}." if selected_skills else ""

        joined = " ".join(part for part in [base_summary, vacancy_part, skills_part] if part).strip()
        return joined[:3000]

    def _build_emphasis(
        self,
        *,
        vacancy: Vacancy | None,
        selected_skills: list[str],
        languages: list[ProfileLanguage],
        links: list[ProfileLink],
    ) -> list[str]:
        hints: list[str] = []
        if vacancy and vacancy.company_name:
            hints.append(f"Компания: {vacancy.company_name}")
        if vacancy and vacancy.title:
            hints.append(f"Роль: {vacancy.title}")
        if selected_skills:
            hints.append(f"Приоритетные навыки: {', '.join(selected_skills[:5])}")
        if languages:
            hints.append(
                "Языки: " + ", ".join(f"{item.language} ({item.level})" for item in languages[:3])
            )
        if links:
            hints.append("Портфолио/ссылки: " + ", ".join(item.url for item in links[:2]))
        return hints


class HHCreateTargetedResumeService:
    def __init__(
        self,
        db: Session,
        *,
        payload_builder: HHTargetedPayloadBuilder,
        automation_client: HHResumeAutomationClient,
    ) -> None:
        self.db = db
        self.payload_builder = payload_builder
        self.automation_client = automation_client
        self.action_control = HHActionControlService(db)

    def create_targeted_resume(self, *, user_id: int, request: HHCreateTargetedResumeRequest) -> tuple[HHManagedResume, HHTargetedResumePayload]:
        request_fingerprint = (
            f"create_targeted_resume:{user_id}:{request.profile_id}:{request.vacancy_id or 'none'}:"
            f"{request.source_resume_version_id or 'none'}:{(request.target_title or '').strip().casefold()}"
        )
        action_decision = self.action_control.start_action(
            user_id=user_id,
            action_type="create_targeted_resume",
            target_type="profile",
            target_id=request.profile_id,
            target_ref=f"vacancy:{request.vacancy_id}" if request.vacancy_id else None,
            request_fingerprint=request_fingerprint,
            min_interval_seconds=3,
            max_concurrent_per_user=2,
        )
        reused_managed_resume_id = (action_decision.reused_context or {}).get("managed_resume_id")
        if action_decision.action_run.status == "duplicate_prevented" and reused_managed_resume_id is not None:
            managed = self.get_managed_resume(user_id=user_id, managed_resume_id=int(reused_managed_resume_id))
            payload = HHTargetedResumePayload(
                profession_title=managed.title or "Специалист",
                summary="Duplicate request skipped; already completed managed resume is reused.",
                education=[],
                skills=[],
                skill_level_hints={},
                work_experience=[],
                targeted_emphasis=[],
            )
            return managed, payload

        try:
            profile = self._owned_profile(profile_id=request.profile_id, user_id=user_id)
            connection = self._require_active_session(user_id=user_id)
            vacancy = self._resolve_vacancy(request.vacancy_id)
            source_resume_version = self._resolve_source_resume_version(
                profile_id=profile.id,
                source_resume_version_id=request.source_resume_version_id,
            )

            payload = self.payload_builder.build(
                profile=profile,
                vacancy=vacancy,
                source_resume_version=source_resume_version,
                request=request,
            )

            managed = HHManagedResume(
                user_id=user_id,
                profile_id=profile.id,
                source_resume_version_id=source_resume_version.id if source_resume_version else None,
                vacancy_id=vacancy.id if vacancy else None,
                title=payload.profession_title,
                status="draft_local" if request.dry_run else "creating",
                desired_visibility_mode="hidden_from_all",
                current_visibility_mode="unknown",
                visibility_status="idle",
            )
            self.db.add(managed)
            self.db.commit()
            self.db.refresh(managed)

            if request.dry_run:
                self.action_control.finish_action(
                    action_run=action_decision.action_run,
                    status_value="completed",
                    operation_code="HH_TARGETED_RESUME_DRY_RUN_COMPLETED",
                    safe_summary="Targeted resume dry run completed without side effects",
                    context_ref={"managed_resume_id": managed.id},
                )
                return managed, payload

            try:
                result = self.automation_client.create_targeted_resume(
                    user_id=user_id,
                    connection=connection,
                    payload=payload,
                    dry_run=False,
                )
            except HHResumeAutomationError as exc:
                managed.status = "failed"
                managed.last_error_code = exc.code[:64]
                managed.last_error_message = "HH automation failed. Reconnect and retry."
                self.db.commit()
                self.db.refresh(managed)
                self.action_control.finish_action(
                    action_run=action_decision.action_run,
                    status_value="retryable_failed",
                    operation_code="HH_TARGETED_RESUME_RETRYABLE_FAILED",
                    safe_summary=f"Targeted resume creation failed with code={exc.code[:32]}",
                    context_ref={"managed_resume_id": managed.id},
                )
                return managed, payload

            managed.status = "created"
            managed.hh_resume_external_id = result.external_id
            managed.hh_resume_url = result.resume_url
            managed.title = result.title
            managed.last_error_code = None
            managed.last_error_message = None
            managed.last_synced_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(managed)
            self.action_control.finish_action(
                action_run=action_decision.action_run,
                status_value="completed",
                operation_code="HH_TARGETED_RESUME_CREATED",
                safe_summary="Targeted resume created and linked to HH external resume",
                context_ref={"managed_resume_id": managed.id},
            )
            return managed, payload
        except HTTPException:
            self.action_control.finish_action(
                action_run=action_decision.action_run,
                status_value="failed",
                operation_code="HH_TARGETED_RESUME_REJECTED",
                safe_summary="Targeted resume action rejected by policy guard",
            )
            raise

    def list_managed_resumes(self, *, user_id: int) -> list[HHManagedResume]:
        items = self.db.query(HHManagedResume).all()
        owned = [item for item in items if item.user_id == user_id]
        return sorted(owned, key=lambda item: (item.updated_at, item.id), reverse=True)

    def get_managed_resume(self, *, user_id: int, managed_resume_id: int) -> HHManagedResume:
        managed = self.db.get(HHManagedResume, managed_resume_id)
        if managed is None or managed.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
        return managed

    def _owned_profile(self, *, profile_id: int, user_id: int) -> Profile:
        profile = self.db.get(Profile, profile_id)
        if profile is None or profile.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
        return profile

    def _resolve_vacancy(self, vacancy_id: int | None) -> Vacancy | None:
        if vacancy_id is None:
            return None
        vacancy = self.db.get(Vacancy, vacancy_id)
        if vacancy is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Vacancy not found")
        return vacancy

    def _resolve_source_resume_version(self, *, profile_id: int, source_resume_version_id: int | None) -> ResumeVersion | None:
        if source_resume_version_id is None:
            return None
        resume_version = self.db.get(ResumeVersion, source_resume_version_id)
        if resume_version is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Resume version not found")
        if resume_version.profile_id != profile_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Resume version belongs to another profile")
        return resume_version

    def _require_active_session(self, *, user_id: int) -> HHBrowserConnection:
        items = self.db.query(HHBrowserConnection).all()
        connection = next((item for item in items if item.user_id == user_id), None)
        if connection is None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Active HH browser session required")
        if connection.status != "connected" or not connection.session_state_ref or connection.requires_reauth:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Active HH browser session required")
        return connection
