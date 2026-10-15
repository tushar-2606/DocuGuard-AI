from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder

from app.config import CORS_ORIGINS, ENVIRONMENT, IS_PRODUCTION
from app.database import init_db
from app.routers import analytics, auth, documents, notifications, tasks
from app.services.reminder_service import (
    shutdown_reminder_scheduler,
    start_reminder_scheduler,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db()
        logger.info("Database initialized successfully.")
    except Exception as exc:
        logger.error("Database initialization failed: %s", type(exc).__name__)
        raise
    start_reminder_scheduler()
    try:
        yield
    finally:
        shutdown_reminder_scheduler()


app = FastAPI(
    title="DocuGuard AI",
    description=(
        "Document intelligence and compliance workspace. "
        "Extraction is deterministic rule-based analysis (not an LLM)."
    ),
    version="2.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(tasks.router)
app.include_router(analytics.router)
app.include_router(notifications.router)


def _safe_error_detail(exc: Exception) -> str:
    if IS_PRODUCTION:
        return "An unexpected error occurred."
    return str(exc)[:300]


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Invalid request data.",
            "errors": jsonable_encoder(exc.errors()),
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        raise exc
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": _safe_error_detail(exc)},
    )


@app.get("/")
async def root():
    return {
        "message": "DocuGuard AI API is running",
        "status": "online",
        "version": "2.1.0",
        "environment": ENVIRONMENT,
        "extraction": "rule_based",
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "DocuGuard AI Backend",
        "version": "2.1.0",
    }
