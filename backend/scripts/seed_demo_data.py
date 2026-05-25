"""Seed reproducible demo data for defense flow.

Usage:
    python scripts/seed_demo_data.py
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.security import hash_password
from app.db.models import (
    Application,
    ApplicationStatusHistory,
    CoverLetterVersion,
    Profile,
    ResumeVersion,
    User,
    Vacancy,
    VacancyScore,
)
from app.db.session import SessionLocal

DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = os.getenv("DEMO_USER_PASSWORD", "demo12345")
DEMO_SOURCE = "demo_seed"


def _upsert_user(db) -> User:
    user = db.scalar(select(User).where(User.email == DEMO_EMAIL))
    if user is None:
        user = User(email=DEMO_EMAIL, password_hash=hash_password(DEMO_PASSWORD), is_active=True)
        db.add(user)
        db.flush()
    else:
        user.password_hash = hash_password(DEMO_PASSWORD)
        user.is_active = True
        db.add(user)
        db.flush()
    return user


def _upsert_profile(db, user: User) -> Profile:
    profile = db.scalar(select(Profile).where(Profile.user_id == user.id).order_by(Profile.id.asc()))
    resume_text = (
        "Python backend engineer with 6+ years of experience in FastAPI, SQLAlchemy, PostgreSQL, "
        "Celery and product development. Focused on reliable APIs, observability and hiring automation."
    )
    if profile is None:
        profile = Profile(
            user_id=user.id,
            title="Backend Python Engineer",
            full_name="Demo Candidate",
            email=DEMO_EMAIL,
            city="Moscow",
            country="Russia",
            remote_ok=True,
            relocation_ok=False,
            salary_min=250000,
            summary_about="Synthetic demo profile for diploma defense. No real personal data used.",
            seniority_level="middle+",
            years_total=6.0,
            preferred_employment="full",
            preferred_schedule="remote",
            preferred_tech=["Python", "FastAPI", "PostgreSQL", "Docker", "Redis"],
            interest_tags=["backend", "api", "microservices"],
            resume_text=resume_text,
            skills_text="Python, FastAPI, SQLAlchemy, PostgreSQL, Redis, Docker, CI/CD",
        )
        db.add(profile)
        db.flush()
        return profile

    profile.title = "Backend Python Engineer"
    profile.full_name = "Demo Candidate"
    profile.email = DEMO_EMAIL
    profile.city = "Moscow"
    profile.country = "Russia"
    profile.remote_ok = True
    profile.relocation_ok = False
    profile.salary_min = 250000
    profile.summary_about = "Synthetic demo profile for diploma defense. No real personal data used."
    profile.seniority_level = "middle+"
    profile.years_total = 6.0
    profile.preferred_employment = "full"
    profile.preferred_schedule = "remote"
    profile.preferred_tech = ["Python", "FastAPI", "PostgreSQL", "Docker", "Redis"]
    profile.interest_tags = ["backend", "api", "microservices"]
    profile.resume_text = resume_text
    profile.skills_text = "Python, FastAPI, SQLAlchemy, PostgreSQL, Redis, Docker, CI/CD"
    db.add(profile)
    db.flush()
    return profile


def _upsert_vacancies(db) -> list[Vacancy]:
    now = datetime.now(timezone.utc)
    rows = [
        ("demo-001", "Backend Python Engineer", "DemoTech", "Remote", 220000, 320000),
        ("demo-002", "Middle Python Developer", "Cloud Garden", "Moscow", 200000, 290000),
        ("demo-003", "FastAPI Engineer", "Neon Apps", "Saint Petersburg", 210000, 300000),
        ("demo-004", "Data Platform Engineer", "Data Orbit", "Remote", 230000, 340000),
        ("demo-005", "Backend Developer (Django/FastAPI)", "Smart Retail", "Kazan", 180000, 260000),
        ("demo-006", "Python Microservices Engineer", "Fin Pilot", "Remote", 240000, 360000),
        ("demo-007", "Integration Engineer", "Api Forge", "Novosibirsk", 190000, 270000),
        ("demo-008", "Backend Engineer", "Demo Logistics", "Yekaterinburg", 200000, 280000),
    ]

    result: list[Vacancy] = []
    for idx, (external_id, title, company, location, salary_from, salary_to) in enumerate(rows):
        vacancy = db.scalar(
            select(Vacancy).where(Vacancy.source == DEMO_SOURCE, Vacancy.external_id == external_id)
        )
        if vacancy is None:
            vacancy = Vacancy(source=DEMO_SOURCE, external_id=external_id, title=title)
        vacancy.company_name = company
        vacancy.location = location
        vacancy.salary_from = salary_from
        vacancy.salary_to = salary_to
        vacancy.currency = "RUR"
        vacancy.status = "open"
        vacancy.published_at = now
        vacancy.url = f"https://example.invalid/vacancy/{external_id}"
        vacancy.description = (
            f"Demo vacancy #{idx + 1}. Stack: Python, FastAPI, PostgreSQL, Redis, Docker. "
            "Synthetic text for defense showcase, no production integration."
        )
        db.add(vacancy)
        db.flush()
        result.append(vacancy)
    return result


def _upsert_scores(db, profile: Profile, vacancies: list[Vacancy]) -> None:
    scores = [
        (0, 0.91, "strong_fit"),
        (1, 0.86, "good_fit"),
    ]
    for idx, final_score, verdict in scores:
        vacancy = vacancies[idx]
        item = db.scalar(
            select(VacancyScore).where(
                VacancyScore.profile_id == profile.id,
                VacancyScore.vacancy_id == vacancy.id,
            )
        )
        if item is None:
            item = VacancyScore(profile_id=profile.id, vacancy_id=vacancy.id, layer1_score=final_score, layer2_score=final_score, final_score=final_score, verdict=verdict, explanation={})
        item.layer1_score = round(final_score - 0.05, 3)
        item.layer2_score = final_score
        item.final_score = final_score
        item.verdict = verdict
        item.explanation = {
            "summary": "Synthetic seeded matching explanation.",
            "highlights": ["Strong Python backend background", "FastAPI and SQL experience"],
            "risks": ["Needs domain onboarding"],
        }
        db.add(item)


def _upsert_resume_versions(db, profile: Profile, vacancies: list[Vacancy]) -> tuple[ResumeVersion, ResumeVersion]:
    draft = db.scalar(select(ResumeVersion).where(ResumeVersion.profile_id == profile.id, ResumeVersion.title == "Demo Draft Resume"))
    if draft is None:
        draft = ResumeVersion(profile_id=profile.id, title="Demo Draft Resume", content_text="Draft resume content for demo defense.", source="llm", status="draft", vacancy_id=vacancies[0].id)
    draft.content_text = "Draft resume content for demo defense. Version intentionally synthetic."
    draft.source = "llm"
    draft.status = "draft"
    draft.vacancy_id = vacancies[0].id
    db.add(draft)

    approved = db.scalar(select(ResumeVersion).where(ResumeVersion.profile_id == profile.id, ResumeVersion.title == "Demo Approved Resume"))
    if approved is None:
        approved = ResumeVersion(profile_id=profile.id, title="Demo Approved Resume", content_text="Approved resume content for demo defense.", source="llm", status="approved", vacancy_id=vacancies[1].id)
    approved.content_text = "Approved resume content for demo defense. Safe synthetic sample."
    approved.source = "llm"
    approved.status = "approved"
    approved.approved_at = datetime.now(timezone.utc)
    approved.vacancy_id = vacancies[1].id
    db.add(approved)

    db.flush()
    return draft, approved


def _upsert_cover_letters(db, profile: Profile, vacancies: list[Vacancy]) -> tuple[CoverLetterVersion, CoverLetterVersion]:
    draft = db.scalar(select(CoverLetterVersion).where(CoverLetterVersion.profile_id == profile.id, CoverLetterVersion.title == "Demo Draft Cover Letter"))
    if draft is None:
        draft = CoverLetterVersion(profile_id=profile.id, title="Demo Draft Cover Letter", subject="Draft application", content_text="Draft cover letter for demo.", source="llm", status="draft", vacancy_id=vacancies[0].id)
    draft.subject = "Draft application"
    draft.content_text = "Draft cover letter for demo defense. Synthetic text only."
    draft.source = "llm"
    draft.status = "draft"
    draft.vacancy_id = vacancies[0].id
    db.add(draft)

    approved = db.scalar(select(CoverLetterVersion).where(CoverLetterVersion.profile_id == profile.id, CoverLetterVersion.title == "Demo Approved Cover Letter"))
    if approved is None:
        approved = CoverLetterVersion(profile_id=profile.id, title="Demo Approved Cover Letter", subject="Approved application", content_text="Approved cover letter for demo.", source="llm", status="approved", vacancy_id=vacancies[1].id)
    approved.subject = "Approved application"
    approved.content_text = "Approved cover letter for demo defense. Safe synthetic sample."
    approved.source = "llm"
    approved.status = "approved"
    approved.approved_at = datetime.now(timezone.utc)
    approved.vacancy_id = vacancies[1].id
    db.add(approved)

    db.flush()
    return draft, approved


def _upsert_applications(db, profile: Profile, vacancies: list[Vacancy], approved_resume: ResumeVersion, approved_cover: CoverLetterVersion) -> None:
    statuses = ["saved", "applied", "hr_screen", "tech_interview", "test_task", "offer", "rejected", "archived"]

    for idx, status in enumerate(statuses):
        vacancy = vacancies[idx % len(vacancies)]
        app = db.scalar(select(Application).where(Application.profile_id == profile.id, Application.vacancy_id == vacancy.id))
        if app is None:
            app = Application(profile_id=profile.id, vacancy_id=vacancy.id, status=status)
        previous = app.status
        app.status = status
        app.note = f"Demo pipeline status: {status}."
        if status in {"applied", "hr_screen", "tech_interview", "test_task", "offer"}:
            app.resume_version_id = approved_resume.id
            app.cover_letter_version_id = approved_cover.id
        db.add(app)
        db.flush()

        history_note = "Seeded status snapshot for demo defense flow."
        history = db.scalar(
            select(ApplicationStatusHistory).where(
                ApplicationStatusHistory.application_id == app.id,
                ApplicationStatusHistory.to_status == status,
                ApplicationStatusHistory.note == history_note,
            )
        )
        if history is None:
            history = ApplicationStatusHistory(
                application_id=app.id,
                from_status=previous if previous != status else None,
                to_status=status,
                note=history_note,
            )
            db.add(history)


def seed_demo_data() -> None:
    db = SessionLocal()
    try:
        user = _upsert_user(db)
        profile = _upsert_profile(db, user)
        vacancies = _upsert_vacancies(db)
        _upsert_scores(db, profile, vacancies)
        _draft_resume, approved_resume = _upsert_resume_versions(db, profile, vacancies)
        _draft_cover, approved_cover = _upsert_cover_letters(db, profile, vacancies)
        _upsert_applications(db, profile, vacancies, approved_resume, approved_cover)
        db.commit()
        print("Demo seed completed successfully")
        print(f"Login email: {DEMO_EMAIL}")
        if "DEMO_USER_PASSWORD" in os.environ:
            print("Password source: DEMO_USER_PASSWORD env var")
        else:
            print("Login password: demo12345")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_demo_data()
