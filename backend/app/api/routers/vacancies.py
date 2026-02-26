from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.db.models import Vacancy, VacancyRequirement
from app.db.session import get_db
from app.schemas.vacancy import VacancyCreate, VacancyRead, VacancyUpdate
from app.services.requirements_extractor import extract_skill_requirements
from app.tasks.embedding_tasks import build_vacancy_embedding

router = APIRouter(prefix="/vacancies", tags=["vacancies"])


def _replace_manual_requirements(db: Session, vacancy: Vacancy) -> None:
    if vacancy.source != "manual":
        return

    db.execute(
        delete(VacancyRequirement).where(
            VacancyRequirement.vacancy_id == vacancy.id,
            VacancyRequirement.kind.in_(("skill", "constraint")),
        )
    )

    requirements_payload = extract_skill_requirements(vacancy.description or "")
    if requirements_payload:
        db.add_all(
            [
                VacancyRequirement(
                    vacancy_id=vacancy.id,
                    kind=requirement["kind"],
                    raw_text=requirement["raw_text"],
                    normalized_key=requirement["normalized_key"],
                    is_hard=requirement["is_hard"],
                    weight=requirement["weight"],
                )
                for requirement in requirements_payload
            ]
        )


@router.post("", response_model=VacancyRead, status_code=status.HTTP_201_CREATED)
def create_vacancy(payload: VacancyCreate, db: Session = Depends(get_db)):
    vacancy = Vacancy(**payload.model_dump())
    db.add(vacancy)
    db.commit()
    db.refresh(vacancy)

    _replace_manual_requirements(db, vacancy)
    db.commit()
    db.refresh(vacancy)

    build_vacancy_embedding.delay(vacancy.id)
    return vacancy


@router.get("", response_model=List[VacancyRead])
def list_vacancies(db: Session = Depends(get_db)):
    return db.query(Vacancy).order_by(Vacancy.id.desc()).all()


@router.get("/{vacancy_id}", response_model=VacancyRead)
def get_vacancy_by_id(vacancy_id: int, db: Session = Depends(get_db)):
    vacancy = db.get(Vacancy, vacancy_id)
    if vacancy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vacancy not found")
    return vacancy


@router.put("/{vacancy_id}", response_model=VacancyRead)
def update_vacancy(vacancy_id: int, payload: VacancyUpdate, db: Session = Depends(get_db)):
    vacancy = db.get(Vacancy, vacancy_id)
    if vacancy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vacancy not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(vacancy, field, value)

    db.commit()
    db.refresh(vacancy)

    _replace_manual_requirements(db, vacancy)
    db.commit()
    db.refresh(vacancy)

    build_vacancy_embedding.delay(vacancy.id)
    return vacancy


@router.delete("/{vacancy_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vacancy(vacancy_id: int, db: Session = Depends(get_db)):
    vacancy = db.get(Vacancy, vacancy_id)
    if vacancy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vacancy not found")

    db.delete(vacancy)
    db.commit()
