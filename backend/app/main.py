from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import clinical_history, consultations, patients

# Initialize FastAPI app with Nurse Amma metadata
app = FastAPI(
    title="Nurse Amma API",
    description=(
        "AI-Powered Multimodal Clinical History-Taking and Medical Document Intelligence "
        "System for Pre-Consultation Healthcare"
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS for the React/TypeScript frontend
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

# Member 1: Clinical History Engine
app.include_router(clinical_history.router)

# Member 3: Patient Management
app.include_router(patients.router)

# Member 3: Consultation Management
app.include_router(consultations.router)

# Member 2: Document Intelligence will be registered
# when that router has been implemented.


@app.get("/", tags=["Health Check"])
async def root():
    """Return API status information."""
    return {
        "status": "online",
        "service": "Nurse Amma API Engine",
        "version": "1.0.0",
        "documentation": "/docs",
    }


@app.get("/health", tags=["Health Check"])
async def health_check():
    """Return the current application status."""
    return {
        "status": "healthy",
        # This is still a placeholder until a real database
        # connectivity check is implemented.
        "database": "connected",
        "modules": {
            "clinical_history": "active",
            "patient_management": "active",
            "consultation_management": "active",
            "document_intelligence": "pending_integration",
            "doctor_dashboard": "pending_integration",
        },
    }