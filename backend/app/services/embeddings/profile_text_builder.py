from __future__ import annotations

from collections import defaultdict
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Profile,
    ProfileAchievement,
    ProfileCertificate,
    ProfileEducation,
    ProfileExperience,
    ProfileLanguage,
    ProfileProject,
    ProfileSkill,
    ResumeVersion,
)

MAX_PROFILE_DOCUMENT_LENGTH = 10_000


def _format_date(value: date | None) -> str:
    if not value:
        return "present"
    return value.strftime("%Y-%m")


def _format_bool(value: bool) -> str:
    return "yes" if value else "no"


def _truncate(text: str, max_length: int = MAX_PROFILE_DOCUMENT_LENGTH) -> str:
    if len(text) <= max_length:
        return text
    return text[: max_length - 3].rstrip() + "..."


def _build_document(
    profile: Profile,
    resume_text: str,
    skills: list[ProfileSkill],
    experiences: list[ProfileExperience],
    projects: list[ProfileProject],
    achievements: list[ProfileAchievement],
    education: list[ProfileEducation],
    certificates: list[ProfileCertificate],
    languages: list[ProfileLanguage],
) -> str:
    parts: list[str] = []

    location = ", ".join(part for part in [profile.city, profile.country] if part)
    profile_summary = [
        f"Title: {profile.title}" if profile.title else None,
        f"Headline: {profile.summary_about}" if profile.summary_about else None,
        f"Location: {location}" if location else None,
        f"Remote: {_format_bool(profile.remote_ok)}",
        f"Relocation: {_format_bool(profile.relocation_ok)}",
        f"Salary min: {profile.salary_min}" if profile.salary_min is not None else None,
        f"Available from: {profile.available_from.isoformat()}" if profile.available_from else None,
        f"Notice period (days): {profile.notice_period_days}"
        if profile.notice_period_days is not None
        else None,
    ]
    parts.append("Profile\n" + "\n".join(line for line in profile_summary if line))

    if resume_text:
        parts.append("Resume\n" + resume_text)

    if skills:
        formatted_skills: list[str] = []
        for skill in skills:
            details = [skill.level] if skill.level else []
            if skill.years is not None:
                details.append(f"{skill.years:g} years")
            if details:
                formatted_skills.append(f"{skill.name_raw} ({', '.join(details)})")
            else:
                formatted_skills.append(skill.name_raw)
        parts.append("Skills\n" + "\n".join(f"- {line}" for line in formatted_skills))

    if experiences:
        exp_lines: list[str] = []
        for exp in experiences:
            date_range = f"{_format_date(exp.start_date)} — {_format_date(exp.end_date if not exp.is_current else None)}"
            exp_lines.append(f"- {exp.position_title} | {exp.company_name} | {date_range}")
            if exp.achievements_text:
                exp_lines.append(f"  Achievements: {exp.achievements_text}")
            if exp.tech_stack_text:
                exp_lines.append(f"  Tech: {exp.tech_stack_text}")
        parts.append("Experience\n" + "\n".join(exp_lines))

    if projects:
        project_lines: list[str] = []
        for project in projects:
            date_range = f"{_format_date(project.start_date)} — {_format_date(project.end_date)}"
            header = f"- {project.name}"
            if project.role:
                header += f" ({project.role})"
            header += f" | {date_range}"
            project_lines.append(header)
            project_lines.append(f"  {project.description_text}")
            if project.tech_stack_text:
                project_lines.append(f"  Tech: {project.tech_stack_text}")
        parts.append("Projects\n" + "\n".join(project_lines))

    if achievements:
        achievement_lines = []
        for achievement in achievements:
            metric = f" [{achievement.metric}]" if achievement.metric else ""
            achievement_lines.append(
                f"- {achievement.title}{metric}: {achievement.description_text}"
            )
        parts.append("Achievements\n" + "\n".join(achievement_lines))

    short_sections: list[str] = []
    if education:
        short_sections.append(
            "Education: "
            + "; ".join(
                f"{item.degree_level}, {item.field_of_study}, {item.institution} ({item.start_year or '?'}-{item.end_year or '?'})"
                for item in education
            )
        )
    if certificates:
        short_sections.append(
            "Certificates: "
            + "; ".join(
                f"{item.name} ({item.issuer})" for item in certificates
            )
        )
    if languages:
        short_sections.append(
            "Languages: "
            + ", ".join(f"{item.language} ({item.level})" for item in languages)
        )
    if short_sections:
        parts.append("Other\n" + "\n".join(short_sections))

    return _truncate("\n\n".join(part for part in parts if part))


def build_profile_documents(db: Session, profile_ids: list[int]) -> dict[int, str]:
    if not profile_ids:
        return {}

    profiles = db.execute(select(Profile).where(Profile.id.in_(profile_ids))).scalars().all()
    profiles_by_id = {profile.id: profile for profile in profiles}

    resume_versions = db.execute(
        select(ResumeVersion)
        .where(
            ResumeVersion.profile_id.in_(profile_ids),
            ResumeVersion.status == "approved",
            ResumeVersion.vacancy_id.is_(None),
        )
        .order_by(
            ResumeVersion.profile_id.asc(),
            ResumeVersion.approved_at.desc().nullslast(),
            ResumeVersion.created_at.desc(),
            ResumeVersion.id.desc(),
        )
    ).scalars().all()

    latest_resume_by_profile: dict[int, str] = {}
    for resume in resume_versions:
        if resume.profile_id not in latest_resume_by_profile:
            latest_resume_by_profile[resume.profile_id] = resume.content_text

    skills_rows = db.execute(
        select(ProfileSkill)
        .where(ProfileSkill.profile_id.in_(profile_ids))
        .order_by(
            ProfileSkill.profile_id.asc(),
            ProfileSkill.is_primary.desc(),
            ProfileSkill.level.desc(),
            ProfileSkill.name_raw.asc(),
        )
    ).scalars().all()
    skills_by_profile: dict[int, list[ProfileSkill]] = defaultdict(list)
    for skill in skills_rows:
        if len(skills_by_profile[skill.profile_id]) < 25:
            skills_by_profile[skill.profile_id].append(skill)

    experience_rows = db.execute(
        select(ProfileExperience)
        .where(ProfileExperience.profile_id.in_(profile_ids))
        .order_by(
            ProfileExperience.profile_id.asc(),
            ProfileExperience.start_date.desc(),
            ProfileExperience.end_date.desc().nullslast(),
            ProfileExperience.id.desc(),
        )
    ).scalars().all()
    experiences_by_profile: dict[int, list[ProfileExperience]] = defaultdict(list)
    for experience in experience_rows:
        if len(experiences_by_profile[experience.profile_id]) < 5:
            experiences_by_profile[experience.profile_id].append(experience)

    project_rows = db.execute(
        select(ProfileProject)
        .where(ProfileProject.profile_id.in_(profile_ids))
        .order_by(
            ProfileProject.profile_id.asc(),
            ProfileProject.start_date.desc().nullslast(),
            ProfileProject.created_at.desc(),
            ProfileProject.id.desc(),
        )
    ).scalars().all()
    projects_by_profile: dict[int, list[ProfileProject]] = defaultdict(list)
    for project in project_rows:
        if len(projects_by_profile[project.profile_id]) < 3:
            projects_by_profile[project.profile_id].append(project)

    achievement_rows = db.execute(
        select(ProfileAchievement)
        .where(ProfileAchievement.profile_id.in_(profile_ids))
        .order_by(
            ProfileAchievement.profile_id.asc(),
            ProfileAchievement.achieved_at.desc().nullslast(),
            ProfileAchievement.created_at.desc(),
            ProfileAchievement.id.desc(),
        )
    ).scalars().all()
    achievements_by_profile: dict[int, list[ProfileAchievement]] = defaultdict(list)
    for achievement in achievement_rows:
        if len(achievements_by_profile[achievement.profile_id]) < 5:
            achievements_by_profile[achievement.profile_id].append(achievement)

    education_rows = db.execute(
        select(ProfileEducation)
        .where(ProfileEducation.profile_id.in_(profile_ids))
        .order_by(
            ProfileEducation.profile_id.asc(),
            ProfileEducation.end_year.desc().nullslast(),
            ProfileEducation.start_year.desc().nullslast(),
            ProfileEducation.id.desc(),
        )
    ).scalars().all()
    education_by_profile: dict[int, list[ProfileEducation]] = defaultdict(list)
    for item in education_rows:
        if len(education_by_profile[item.profile_id]) < 3:
            education_by_profile[item.profile_id].append(item)

    certificate_rows = db.execute(
        select(ProfileCertificate)
        .where(ProfileCertificate.profile_id.in_(profile_ids))
        .order_by(
            ProfileCertificate.profile_id.asc(),
            ProfileCertificate.issued_at.desc().nullslast(),
            ProfileCertificate.id.desc(),
        )
    ).scalars().all()
    certificates_by_profile: dict[int, list[ProfileCertificate]] = defaultdict(list)
    for item in certificate_rows:
        if len(certificates_by_profile[item.profile_id]) < 5:
            certificates_by_profile[item.profile_id].append(item)

    language_rows = db.execute(
        select(ProfileLanguage)
        .where(ProfileLanguage.profile_id.in_(profile_ids))
        .order_by(
            ProfileLanguage.profile_id.asc(),
            ProfileLanguage.id.asc(),
        )
    ).scalars().all()
    languages_by_profile: dict[int, list[ProfileLanguage]] = defaultdict(list)
    for item in language_rows:
        if len(languages_by_profile[item.profile_id]) < 5:
            languages_by_profile[item.profile_id].append(item)

    documents: dict[int, str] = {}
    for profile_id in profile_ids:
        profile = profiles_by_id.get(profile_id)
        if not profile:
            continue

        resume_text = latest_resume_by_profile.get(profile_id) or profile.resume_text or ""
        documents[profile_id] = _build_document(
            profile=profile,
            resume_text=resume_text,
            skills=skills_by_profile.get(profile_id, []),
            experiences=experiences_by_profile.get(profile_id, []),
            projects=projects_by_profile.get(profile_id, []),
            achievements=achievements_by_profile.get(profile_id, []),
            education=education_by_profile.get(profile_id, []),
            certificates=certificates_by_profile.get(profile_id, []),
            languages=languages_by_profile.get(profile_id, []),
        )

    return documents


def build_profile_document(db: Session, profile_id: int) -> str:
    return build_profile_documents(db, [profile_id]).get(profile_id, "")
