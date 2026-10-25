from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import engine
from app.routers import (
    clinical_history,
    consultations,
    documents,
    patients,
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


# Configure CORS for the React/TypeScript frontend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Member 1: Clinical history, speech, and summary services.
app.include_router(clinical_history.router)

# Member 3: Patient management.
app.include_router(patients.router)

# Member 3: Consultation management.
app.include_router(consultations.router)

# Member 2: Medical document processing and OCR.
# The document router defines the "/documents" prefix.
# This creates routes under "/api/v1/documents".
app.include_router(
    documents.router,
    prefix="/api/v1",
)


@app.get("/", tags=["Health Check"])
async def root():
    """Return API status information."""
    return {
        "status": "online",
        "service": "Nurse Amma API",
        "version": "1.0.0",
        "documentation": "/docs",
    }


@app.get("/health", tags=["Health Check"])
def health_check():
    """Check API health and database connectivity."""
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
            "clinical_history": "active",
            "patient_management": "active",
            "consultation_management": "active",
            "document_intelligence": "active",
            "doctor_dashboard": "pending_integration",
        },
    }