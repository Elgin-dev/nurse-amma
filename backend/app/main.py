from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.db.session import engine
from app.routers import (
    auth,
    clinical_history,
    consultations,
    documents,
    patients,
    reviews,
    timeline,
)


app = FastAPI(
    title="Nurse Amma API",
    description=(
        "AI-Powered Multimodal Clinical History-Taking "
        "and Medical Document Intelligence System "
        "for Pre-Consultation Healthcare"
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Authentication routes are public only for bootstrap/login. Protected operations
# require a signed Bearer access token and record-level authorization.
app.include_router(auth.router)
app.include_router(clinical_history.router)
app.include_router(patients.router)
app.include_router(consultations.router)
app.include_router(documents.router, prefix="/api/v1")
app.include_router(timeline.router)
app.include_router(reviews.router)

TEST_UI_PATH = Path(__file__).resolve().parent.parent / "test_ui.html"


@app.get("/", tags=["Health Check"])
async def root():
    return {
        "status": "online",
        "service": "Nurse Amma API",
        "version": "1.0.0",
        "documentation": "/docs",
    }


@app.get("/test-ui", include_in_schema=False)
def test_ui():
    return FileResponse(TEST_UI_PATH, media_type="text/html")


@app.get("/health", tags=["Health Check"])
def health_check():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "database": "disconnected",
                "modules": {
                    "authentication": "registered",
                    "clinical_history": "registered",
                    "patient_management": "registered",
                    "consultation_management": "registered",
                    "document_intelligence": "registered",
                    "doctor_dashboard": "pending_integration",
                },
            },
        )

    return {
        "status": "healthy",
        "database": "connected",
        "modules": {
            "authentication": "active",
            "clinical_history": "active",
            "patient_management": "active",
            "consultation_management": "active",
            "document_intelligence": "active",
            "doctor_dashboard": "pending_integration",
        },
    }