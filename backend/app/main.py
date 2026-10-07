from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.routers import analytics, auth, documents, tasks

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize SQLite database and tables
    try:
        init_db()
        logger.info("Database initialized successfully.")
    except Exception as exc:
        logger.error(f"Database initialization failed: {exc}")
    yield


app = FastAPI(
    title="DocuGuard AI",
    description="Production-grade AI document intelligence and compliance SaaS platform",
    version="2.0.0",
    lifespan=lifespan,
)

# --------------------------------------------------
# CORS
# --------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------------------------
# Routers
# --------------------------------------------------

app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(tasks.router)
app.include_router(analytics.router)


# --------------------------------------------------
# Health Check & Root
# --------------------------------------------------

@app.get("/")
async def root():
    return {
        "message": "DocuGuard AI API is running",
        "status": "online",
        "version": "2.0.0",
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "DocuGuard AI Backend",
    }