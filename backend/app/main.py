import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers.imports import router as imports_router
from app.api.routers.vacancies import router as vacancies_router

app = FastAPI(title="Job Search App")

origins_raw = os.getenv("CORS_ORIGINS", "")
origins = [o.strip() for o in origins_raw.split(",") if o.strip()] or ["http://localhost:5173"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"message": "Hello! Go to /docs"}


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(vacancies_router, prefix="/api/v1")

app.include_router(imports_router, prefix="/api/v1")
