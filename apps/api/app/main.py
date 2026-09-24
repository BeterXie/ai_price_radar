from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from contextlib import suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import get_settings
from .core.runtime_safety import validate_api_runtime_settings
from .database import Base, engine
from .routers import admin, auth, discovery, internal, public, public_feed, user
from .seed import seed

settings = get_settings()
VERSION = "3.9.1"
PRIVACY_CLEANUP_INTERVAL_SECONDS = 24 * 60 * 60
logger = logging.getLogger(__name__)


async def _privacy_cleanup_loop(session_factory) -> None:
    while True:
        await asyncio.sleep(PRIVACY_CLEANUP_INTERVAL_SECONDS)

        def run_cleanup() -> None:
            from .services.privacy import cleanup_privacy_data

            with session_factory() as db:
                cleanup_privacy_data(db)

        try:
            await asyncio.to_thread(run_cleanup)
        except Exception:
            logger.exception("Periodic privacy cleanup failed")


@asynccontextmanager
async def lifespan(_: FastAPI):
    validate_api_runtime_settings(settings)
    Base.metadata.create_all(bind=engine)
    from .services.db_migration import ensure_db_schema
    ensure_db_schema(engine)
    from .database import SessionLocal
    from .services.auth import migrate_legacy_session_tokens
    from .services.credential_crypto import migrate_bot_credentials
    from .services.privacy import cleanup_privacy_data

    if settings.seed_demo_data:
        seed()
    else:
        from .services.community_skills import seed_default_community_skills
        with SessionLocal() as db:
            seed_default_community_skills(db)

    with SessionLocal() as db:
        migrate_legacy_session_tokens(db)
        migrate_bot_credentials(db)
        cleanup_privacy_data(db)

    privacy_cleanup_task = asyncio.create_task(_privacy_cleanup_loop(SessionLocal))

    try:
        from extensions.bots.qq_gateway import qq_gateway_service

        qq_gateway_service.start()
        print(">>> [FastAPI Lifespan] QQ Gateway service started <<<", flush=True)
    except Exception as exc:
        print(f">>> [FastAPI Lifespan] QQ Gateway service failed: {exc} <<<", flush=True)

    try:
        yield
    finally:
        privacy_cleanup_task.cancel()
        with suppress(asyncio.CancelledError):
            await privacy_cleanup_task
        try:
            from extensions.bots.qq_gateway import qq_gateway_service

            await qq_gateway_service.stop()
        except Exception:
            pass



app = FastAPI(
    title=settings.app_name,
    version=VERSION,
    lifespan=lifespan,
    docs_url="/docs" if settings.api_docs_enabled else None,
    redoc_url=None,
    openapi_url="/openapi.json" if settings.api_docs_enabled else None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count"],
)
app.include_router(public.router)
app.include_router(public_feed.router)
app.include_router(auth.router)
app.include_router(user.router)
app.include_router(admin.router)
app.include_router(internal.router)
app.include_router(internal.detector_router)
app.include_router(discovery.router)
app.include_router(discovery.runs_router)
discovery.register_discovery_payload_guard(app)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": VERSION}
