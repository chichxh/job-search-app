import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
