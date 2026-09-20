from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import get_settings
from .database import Base, engine
from .routers import admin, auth, discovery, internal, public, public_feed, user
from .seed import seed

settings = get_settings()
VERSION = "3.7.95"


@asynccontextmanager
async def lifespan(_: FastAPI):
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

    try:
        from extensions.bots.qq_gateway import qq_gateway_service

        qq_gateway_service.start()
        print(">>> [FastAPI Lifespan] QQ Gateway service started <<<", flush=True)
    except Exception as exc:
        print(f">>> [FastAPI Lifespan] QQ Gateway service failed: {exc} <<<", flush=True)

    yield

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
