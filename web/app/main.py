from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.config import settings
from app.db import async_session_factory
from app.routes import entries, export, pages
from app.schemas import HealthResponse

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

STATIC_DIR = Path(__file__).parent / "static"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    logger.info("Starting Pascal Web Logger")
    logger.info("Timezone: %s", settings.timezone)
    logger.info("Database: %s", settings.database_url)
    yield
    logger.info("Shutting down Pascal Web Logger")


app = FastAPI(
    title="Pascal Web Logger",
    description="Web app for logging Pascal the puppy's activities",
    version="0.1.0",
    lifespan=lifespan,
)

# Mount static files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Include routers
app.include_router(pages.router)
app.include_router(entries.router)
app.include_router(export.router)


@app.get("/healthz", response_model=HealthResponse)
async def healthz() -> HealthResponse:
    """Health check endpoint."""
    db_status = "ok"
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
    except Exception as e:
        logger.error("Database health check failed: %s", e)
        db_status = "error"

    return HealthResponse(status="ok", database=db_status)
