"""FastAPI application entry point."""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .routes import emails, therapists
from .schemas import HealthResponse

# Create FastAPI app
app = FastAPI(
    title="Therapist Finder API",
    description="API for parsing therapist data and generating email drafts",
    version="1.0.0",
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    """Handle ValueError as 400 Bad Request."""
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc), "code": "VALIDATION_ERROR"},
    )


@app.exception_handler(FileNotFoundError)
async def not_found_handler(request: Request, exc: FileNotFoundError) -> JSONResponse:
    """Handle FileNotFoundError as 404."""
    return JSONResponse(
        status_code=404,
        content={"detail": str(exc), "code": "NOT_FOUND"},
    )


# Health check
@app.get("/api/health", response_model=HealthResponse, tags=["health"])
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse()


# Register API routes
app.include_router(therapists.router, prefix="/api")
app.include_router(emails.router, prefix="/api")


# Serve frontend static files
frontend_path = Path(__file__).parent.parent.parent / "frontend"
if frontend_path.exists():
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
