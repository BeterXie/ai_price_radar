from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import get_settings
from .database import Base, engine
from .routers import admin, discovery, internal, public
from .seed import seed

settings = get_settings()
VERSION = "3.7.11"


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    if settings.seed_demo_data:
        seed()
    yield


app = FastAPI(
    title=settings.app_name,
    version=VERSION,
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(public.router)
app.include_router(admin.router)
app.include_router(internal.router)
app.include_router(internal.detector_router)
app.include_router(discovery.router)
app.include_router(discovery.runs_router)
discovery.register_discovery_payload_guard(app)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": VERSION}
