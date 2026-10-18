"""
Main Application Factory for Smart LPG Safety System.
Initializes FastAPI, mounts the REST API router, serves static dashboard files,
and orchestrates background simulation workers via Lifespan.
"""

from __future__ import annotations
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import BASE_DIR, settings
from backend.routes import api_router
from backend.service import coordinator


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown lifecycle."""
    # Startup: Launch background simulation worker
    coordinator.start_background_loop()
    yield
    # Shutdown: Cleanly stop background worker
    coordinator.stop_background_loop()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    app = FastAPI(
        title="Smart LPG Leak Detection & Automatic Shut-Off System",
        description=(
            "An academic IoT simulation prototype for continuous LPG/gas monitoring, "
            "rate-of-rise abnormal detection, multi-level alert escalations, and automated "
            "servo valve shut-off protection."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )

    # Enable CORS for local cross-origin development if needed
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount REST API router
    app.include_router(api_router)

    # Mount Static Frontend
    frontend_dir = BASE_DIR / "frontend"
    if frontend_dir.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

    return app


app = create_app()

