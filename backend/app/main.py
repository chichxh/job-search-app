import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers.vacancies import router as vacancies_router

app = FastAPI(title="Job Search App")

origins_raw = os.getenv("CORS_ORIGINS", "")
origins = [o.strip() for o in origins_raw.split(",") if o.strip()]

# Всегда разрешаем локальные dev-origin'ы, чтобы фронтенд работал
# независимо от того, открыт ли он через localhost или 127.0.0.1.
default_local_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

for origin in default_local_origins:
    if origin not in origins:
        origins.append(origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
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
