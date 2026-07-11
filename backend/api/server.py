"""FastAPI application factory."""
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

import api.event_queue as eq
from api.database import init_db
from core import tracker

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── startup ──────────────────────────────────────────────────────────────
    init_db()                        # create tables + default Config row
    await eq.start_relay()           # start the sync→async event relay
    tracker.set_event_queue(eq.sync_q)  # inject queue into tracker module
    logger.info("Smart Job Assistant API started")
    yield
    # ── shutdown ──────────────────────────────────────────────────────────────
    import api.session_manager as sm
    sm.stop()
    logger.info("Smart Job Assistant API shutting down")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Smart Job Assistant API",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://localhost:5173",   # Vite dev server
            "http://localhost:5174",   # Vite dev server (alternate)
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:5174",
            "http://localhost:8001",
            "http://127.0.0.1:8001",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from api.routes import auth, config, cv, session, history, review, reports, ignored_jobs, ws, system, naukri, interview
    app.include_router(auth.router)
    app.include_router(config.router)
    app.include_router(cv.router)
    app.include_router(session.router)
    app.include_router(history.router)
    app.include_router(review.router)
    app.include_router(reports.router)
    app.include_router(ignored_jobs.router)
    app.include_router(ws.router)
    app.include_router(system.router)
    app.include_router(naukri.router)
    app.include_router(interview.router)

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    _mount_frontend(app)

    return app


class _SPAStaticFiles(StaticFiles):
    """Static file server with SPA fallback — unknown paths return index.html
    so client-side routes (e.g. /dashboard) survive a page refresh."""

    async def get_response(self, path: str, scope):
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404:
                return await super().get_response("index.html", scope)
            raise
        if response.status_code == 404:
            response = await super().get_response("index.html", scope)
        return response


def _frontend_dist_dir() -> Path | None:
    """Locate the built frontend (frontend/dist)."""
    env_dir = os.getenv("FRONTEND_DIST", "").strip()
    if env_dir:
        p = Path(env_dir)
        return p if p.is_dir() else None
    # PyInstaller bundle: dist ships next to the executable under _internal
    if getattr(sys, "frozen", False):
        bundled = Path(getattr(sys, "_MEIPASS", "")) / "frontend_dist"
        if bundled.is_dir():
            return bundled
    # Dev checkout: <repo>/frontend/dist
    local = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
    return local if local.is_dir() else None


def _mount_frontend(app: FastAPI) -> None:
    dist = _frontend_dist_dir()
    if dist and (dist / "index.html").is_file():
        app.mount("/", _SPAStaticFiles(directory=str(dist), html=True), name="frontend")
        logger.info("Serving frontend from %s", dist)


app = create_app()
