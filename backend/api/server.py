"""FastAPI application factory."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import api.event_queue as eq
from api.database import init_db
import core.tracker as tracker

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
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from api.routes import auth, config, cv, session, history, ws
    app.include_router(auth.router)
    app.include_router(config.router)
    app.include_router(cv.router)
    app.include_router(session.router)
    app.include_router(history.router)
    app.include_router(ws.router)

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()
