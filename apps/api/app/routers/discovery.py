from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import SourceCandidate, SourceDiscoveryRun
from ..schemas import (
    DiscoveryCandidateBatch,
    DiscoveryCandidateClaimOut,
    DiscoveryCandidateClaimRequest,
    DiscoveryCandidateResult,
    DiscoveryCandidateUpsert,
    DiscoveryRunCreate,
    DiscoveryRunFinish,
)
from ..security import require_discovery_worker
from ..services.source_discovery import (
    claim_candidates,
    report_candidate_result,
    upsert_candidate,
)
from ..services.source_policy import policy_check
from ..services.source_intake import utcnow


router = APIRouter(
    prefix="/api/v1/internal/source-candidates",
    tags=["internal-source-candidates"],
    dependencies=[Depends(require_discovery_worker)],
)

runs_router = APIRouter(
    prefix="/api/v1/internal/source-discovery",
    tags=["internal-source-discovery"],
    dependencies=[Depends(require_discovery_worker)],
)

policy_router = APIRouter(
    prefix="/api/v1/internal/source-policy",
    tags=["internal-source-policy"],
    dependencies=[Depends(require_discovery_worker)],
)

KNOWN_ADAPTERS = frozenset({"seed", "bing", "github", "commoncrawl", "manual"})
MAX_PAYLOAD_BYTES = 1024 * 1024


def register_discovery_payload_guard(app: FastAPI) -> None:
    @app.middleware("http")
    async def _discovery_payload_guard(request: Request, call_next):
        path = request.url.path
        if path.startswith("/api/v1/internal/source-candidates") or path.startswith(
            "/api/v1/internal/source-discovery"
        ):
            try:
                content_length = int(request.headers.get("content-length") or 0)
            except (TypeError, ValueError):
                return JSONResponse(status_code=411, content={"detail": "Content-Length is required"})
            if content_length <= 0 or content_length > MAX_PAYLOAD_BYTES:
                return JSONResponse(
                    status_code=413,
                    content={"detail": "discovery payload exceeds size limit"},
                )
        return await call_next(request)


def _candidate_summary(candidate: SourceCandidate) -> dict[str, object]:
    return {
        "candidate_id": candidate.id,
        "status": candidate.status,
        "detected_platform": candidate.detected_platform,
        "detected_source_url": candidate.detected_source_url,
        "detected_source_key": candidate.detected_source_key,
        "ai_product_count": candidate.ai_product_count,
        "promoted_intake_id": candidate.promoted_intake_id,
        "next_verify_at": candidate.next_verify_at,
    }


@router.post("/upsert")
def upsert_source_candidate(
    payload: DiscoveryCandidateUpsert,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    if payload.run_id is not None:
        run = db.get(SourceDiscoveryRun, payload.run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="discovery run not found")
        if run.status != "running":
            raise HTTPException(status_code=409, detail="discovery run is not running")
    try:
        result = upsert_candidate(
            db,
            discovered_url=payload.discovered_url,
            platform_hint=payload.platform_hint,
            discovered_by=payload.discovered_by,
            matched_query=payload.matched_query,
            run_id=payload.run_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except IntegrityError:
        raise HTTPException(status_code=409, detail="concurrent candidate upsert conflict") from None
    db.commit()
    return result


@router.post("/batch")
def batch_upsert_source_candidates(
    payload: DiscoveryCandidateBatch,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    items: list[dict[str, object]] = []
    for item in payload.items:
        if item.run_id is not None:
            run = db.get(SourceDiscoveryRun, item.run_id)
            if run is None:
                raise HTTPException(status_code=404, detail=f"discovery run {item.run_id} not found")
            if run.status != "running":
                raise HTTPException(status_code=409, detail=f"discovery run {item.run_id} is not running")
        try:
            result = upsert_candidate(
                db,
                discovered_url=item.discovered_url,
                platform_hint=item.platform_hint,
                discovered_by=item.discovered_by,
                matched_query=item.matched_query,
                run_id=item.run_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        items.append(result)
    db.commit()
    return {"items": items}


@router.post("/claim", response_model=list[DiscoveryCandidateClaimOut])
def claim_source_candidates(
    payload: DiscoveryCandidateClaimRequest,
    db: Session = Depends(get_db),
) -> list[DiscoveryCandidateClaimOut]:
    rows = claim_candidates(db, limit=payload.limit, lease_seconds=payload.lease_seconds)
    return [
        DiscoveryCandidateClaimOut(
            candidate_id=row.id,
            candidate_key=row.candidate_key,
            canonical_url=row.canonical_url,
            platform_hint=row.platform_hint,
            attempt_count=row.attempt_count,
            lease_expires_at=row.lease_expires_at,
        )
        for row in rows
    ]


@router.post("/{candidate_id}/result")
def report_source_candidate_result(
    candidate_id: int,
    payload: DiscoveryCandidateResult,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    try:
        candidate = report_candidate_result(
            db,
            candidate_id=candidate_id,
            attempt_count=payload.attempt_count,
            status=payload.status,
            detected_platform=payload.detected_platform,
            detected_source_key=payload.detected_source_key,
            detected_source_url=payload.detected_source_url,
            total_product_count=payload.total_product_count,
            ai_product_count=payload.ai_product_count,
            sample_products=payload.sample_products,
            fingerprints=payload.fingerprints,
            confidence_score=payload.confidence_score,
            failure_reason=payload.failure_reason,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _candidate_summary(candidate)


@runs_router.post("/runs")
def create_discovery_run(
    payload: DiscoveryRunCreate,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    adapters = list(dict.fromkeys(value.strip() for value in payload.adapters if value.strip()))
    unknown = sorted(set(adapters) - KNOWN_ADAPTERS)
    if unknown:
        raise HTTPException(status_code=422, detail=f"unknown discovery adapters: {', '.join(unknown)}")
    run = SourceDiscoveryRun(
        trigger=payload.trigger,
        adapters=adapters,
        status="running",
        started_at=utcnow(),
    )
    db.add(run)
    db.commit()
    return {"run_id": run.id, "status": run.status}


@runs_router.post("/runs/{run_id}/finish")
def finish_discovery_run(
    run_id: int,
    payload: DiscoveryRunFinish,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    run = db.get(SourceDiscoveryRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="discovery run not found")
    if run.status != "running":
        raise HTTPException(status_code=409, detail=f"discovery run is already {run.status}")
    run.status = payload.status
    run.finished_at = utcnow()
    run.discovered_raw_count = payload.discovered_raw_count
    run.normalized_count = payload.normalized_count
    run.duplicate_count = payload.duplicate_count
    run.new_candidate_count = payload.new_candidate_count
    run.reverified_count = payload.reverified_count
    run.adapter_stats = payload.adapter_stats
    run.note = payload.note
    db.commit()
    return {"run_id": run.id, "status": run.status}


@policy_router.get("/check")
def check_source_policy(source_url: str, db: Session = Depends(get_db)) -> dict[str, object]:
    try:
        return policy_check(db, source_url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
