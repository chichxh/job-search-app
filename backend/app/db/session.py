import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker, DeclarativeBase


class Base(DeclarativeBase):
    pass


DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://jobuser:jobpass@db:5432/jobdb")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, class_=Session)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
