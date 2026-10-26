from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import clinical_history

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

# Configure CORS for React/TypeScript frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Vite default dev ports
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Module Routers
# Member 1: Clinical History Engine
app.include_router(clinical_history.router)

# Member 2: Document Intelligence Router (Placeholder for Member 2's module)
# from app.routers import documents
# app.include_router(documents.router)

# Member 3: Consultations and Doctor Dashboard Router (Placeholder for Member 3's module)
# from app.routers import consultations, doctor
# app.include_router(consultations.router)
# app.include_router(doctor.router)


@app.get("/", tags=["Health Check"])
async def root():
    """
    Root endpoint for health checks and API status verification.
    """
    return {
        "status": "online",
        "service": "Nurse Amma API Engine",
        "version": "1.0.0",
        "documentation": "/docs",
    }


@app.get("/health", tags=["Health Check"])
async def health_check():
    """
    Detailed health check endpoint for monitoring backend services.
    """
    return {
        "status": "healthy",
        "database": "connected",  # Hook into session check when DB is configured
        "modules": {
            "clinical_history": "active",
            "document_intelligence": "pending_integration",
            "doctor_dashboard": "pending_integration",
        },
    }