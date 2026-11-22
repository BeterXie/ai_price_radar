from __future__ import annotations

import asyncio
import os
import secrets
import tempfile
import gzip
import zlib
from datetime import datetime, timedelta, timezone
from hmac import compare_digest
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from ..core.config import get_settings
from ..database import SessionLocal, get_db
from ..models import CollectorJob
from ..services.collector_protocol import MAX_COMPRESSED, parse_bundle


def require_collector(x_collector_worker_key: str = Header(default="")):
    settings = get_settings()
    expected = settings.collector_worker_key
    if not settings.collector_enabled or len(expected) < 32:
        raise HTTPException(503, "collector is disabled")
    if not compare_digest(x_collector_worker_key.encode(), expected.encode()):
        raise HTTPException(401, "invalid collector key")


router = APIRouter(prefix="/api/v1/internal/collectors", dependencies=[Depends(require_collector)], tags=["collectors"])


class Claim(BaseModel):
    worker_id: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_.-]+$")
    release: str = Field(min_length=1, max_length=30)


class Lease(BaseModel):
    token: str = Field(pattern=r"^[a-f0-9]{48}$")


class Failure(Lease):
    error: str = Field(min_length=1, max_length=500)
    retryable: bool = True


def utcnow():
    return datetime.now(timezone.utc)


def _active(job, token):
    expiry = job.lease_expires_at
    if expiry is not None and expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    if job.status not in {"running", "receiving"} or not compare_digest(job.lease_token.encode(), token.encode()) or expiry is None or expiry <= utcnow():
        raise HTTPException(409, "collector lease is no longer active")


@router.post("/claim")
def claim(payload: Claim, db: Session = Depends(get_db)):
    now = utcnow()
    job = db.scalar(select(CollectorJob).where(
        CollectorJob.release == payload.release,
        or_(CollectorJob.status == "queued", and_(CollectorJob.status.in_(("running", "receiving", "retry")), CollectorJob.lease_expires_at <= now)),
        CollectorJob.attempts < 5,
    ).order_by(CollectorJob.created_at).with_for_update(skip_locked=True).limit(1))
    if job is None:
        return None
    job.status = "running"
    job.worker_id = payload.worker_id
    job.lease_token = secrets.token_hex(24)
    job.attempts += 1
    job.lease_expires_at = now + timedelta(minutes=5)
    job.updated_at = now
    db.commit()
    return {"id": job.id, "kind": job.kind, "release": job.release, "sources": job.sources,
            "token": job.lease_token, "created_at": job.created_at.isoformat(), "attempt": job.attempts}


@router.post("/{job_id}/heartbeat")
def heartbeat(job_id: UUID, payload: Lease, db: Session = Depends(get_db)):
    job = db.scalar(select(CollectorJob).where(CollectorJob.id == str(job_id)).with_for_update())
    if job is None:
        raise HTTPException(404, "unknown collector job")
    _active(job, payload.token)
    job.lease_expires_at = utcnow() + timedelta(minutes=5)
    job.updated_at = utcnow()
    db.commit()
    return {"ok": True}


@router.post("/{job_id}/failure")
def failure(job_id: UUID, payload: Failure, db: Session = Depends(get_db)):
    job = db.scalar(select(CollectorJob).where(CollectorJob.id == str(job_id)).with_for_update())
    if job is None:
        raise HTTPException(404, "unknown collector job")
    _active(job, payload.token)
    # Preserve the batch and local checkpoints for a retry, with a cooldown.
    job.error = payload.error
    job.lease_token = ""
    job.status = "retry"
    job.lease_expires_at = utcnow() + timedelta(minutes=5)
    if job.attempts >= 5 or not payload.retryable:
        job.status, job.active_lane = "failed", None
    db.commit()
    return {"ok": True}


@router.put("/{job_id}/result")
async def result(job_id: UUID, request: Request, x_collector_lease: str = Header(default="")):
    import re
    if not re.fullmatch(r"[a-f0-9]{48}", x_collector_lease):
        raise HTTPException(401, "invalid collector lease")
    identity = str(job_id)
    directory = Path(get_settings().collector_results_dir)
    directory.mkdir(parents=True, exist_ok=True)
    def task_info():
        with SessionLocal() as db:
            job = db.scalar(select(CollectorJob).where(CollectorJob.id == identity).with_for_update())
            if job is None:
                raise HTTPException(404, "unknown collector job")
            if job.status in {"collected", "publishing", "published"} and compare_digest(job.lease_token, x_collector_lease):
                return None
            _active(job, x_collector_lease)
            if job.status == "receiving":
                raise HTTPException(409, "collection upload is already in progress")
            job.status = "receiving"
            db.commit()
            return job.sources
    sources = await asyncio.to_thread(task_info)
    if sources is None:
        return {"ok": True, "already_received": True}
    target = directory / f"{identity}-{uuid4().hex}.jsonl.gz"
    accepted = False
    uncertain_commit = False
    try:
        received = 0
        # Full multi-source bundles can take several minutes over the private
        # SSH link. Heartbeats keep the lease active during this bounded upload.
        async with asyncio.timeout(900):
            with target.open("xb") as stream:
                async for chunk in request.stream():
                    received += len(chunk)
                    if received > MAX_COMPRESSED:
                        raise HTTPException(413, "collector result exceeds size limit")
                    await asyncio.to_thread(stream.write, chunk)
                stream.flush()
                await asyncio.to_thread(os.fsync, stream.fileno())
        # Persist the directory entry before committing its name to PostgreSQL.
        if os.name == "posix":
            descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                await asyncio.to_thread(os.fsync, descriptor)
            finally:
                os.close(descriptor)
        def validate_and_accept():
            with tempfile.TemporaryDirectory(prefix="validate-", dir=directory) as unpack:
                try:
                    summaries = parse_bundle(target, identity, sources, Path(unpack))
                except (ValueError, gzip.BadGzipFile, zlib.error, EOFError) as exc:
                    raise HTTPException(422, "invalid or incomplete collector bundle") from exc
            with SessionLocal() as db:
                job = db.scalar(select(CollectorJob).where(CollectorJob.id == identity).with_for_update())
                _active(job, x_collector_lease)
                job.result_file = target.name
                job.result_summary = {"sources": len(summaries), "records": sum(x["count"] for x in summaries),
                                      "failures": sum(x["status"] != "ok" for x in summaries)}
                job.status = "collected"
                job.lease_expires_at = None
                job.updated_at = utcnow()
                db.commit()
                return job.result_summary
        validation = asyncio.create_task(asyncio.to_thread(validate_and_accept))
        validation.add_done_callback(lambda task: task.exception() if not task.cancelled() else None)
        try:
            summary = await asyncio.shield(validation)
            accepted = True
        except asyncio.CancelledError:
            # The shielded thread retains ownership of the artifact. Repeated
            # request cancellation must never delete a possibly committed file.
            uncertain_commit = True
            raise
        return {"ok": True, "summary": summary}
    except SQLAlchemyError:
        # COMMIT may have reached PostgreSQL even if its reply was lost. Keep
        # the artifact; the orphan collector can remove an unreferenced file.
        uncertain_commit = True
        raise
    finally:
        if not accepted:
            if not uncertain_commit:
                target.unlink(missing_ok=True)
            def reset_receiving():
                with SessionLocal() as db:
                    from sqlalchemy import update
                    db.execute(update(CollectorJob).where(CollectorJob.id == identity, CollectorJob.status == "receiving",
                        CollectorJob.lease_token == x_collector_lease).values(status="running"))
                    db.commit()
            if not uncertain_commit:
                await asyncio.to_thread(reset_receiving)
