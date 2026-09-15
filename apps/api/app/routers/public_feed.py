from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException, Response, status
from fastapi.responses import FileResponse, JSONResponse

router = APIRouter(tags=["public-feed"])

# Search possible locations for data folder
CANDIDATE_DATA_DIRS = [
    Path(__file__).resolve().parents[4] / "apps" / "web" / "public" / "data",
    Path(__file__).resolve().parents[3] / "web" / "public" / "data",
    Path("/workspace/apps/web/public/data"),
    Path("/opt/ai-price-radar-v3/apps/web/public/data"),
    Path("./data"),
]


def _find_data_dir() -> Path:
    for candidate in CANDIDATE_DATA_DIRS:
        if candidate.is_dir():
            return candidate
    # Fallback to the primary candidate
    return CANDIDATE_DATA_DIRS[0]


@router.get("/data/latest.json")
def get_latest_feed(if_none_match: str | None = Header(None)) -> Response:
    data_dir = _find_data_dir()
    latest_file = data_dir / "latest.json"
    if not latest_file.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Latest snapshot feed has not been generated yet",
        )

    content = latest_file.read_bytes()
    etag = f'"{hashlib.sha256(content).hexdigest()[:16]}"'

    if if_none_match and if_none_match.strip('"') == etag.strip('"'):
        return Response(
            status_code=status.HTTP_304_NOT_MODIFIED,
            headers={
                "ETag": etag,
                "Cache-Control": "public, max-age=60, stale-while-revalidate=300",
            },
        )

    return Response(
        content=content,
        media_type="application/json",
        headers={
            "ETag": etag,
            "Cache-Control": "public, max-age=60, stale-while-revalidate=300",
            "Access-Control-Allow-Origin": "*",
        },
    )


@router.get("/data/v1/snapshots/{snapshot_id}.json")
def get_snapshot_feed(snapshot_id: str, if_none_match: str | None = Header(None)) -> Response:
    # Ensure safe filename
    safe_id = "".join(c for c in snapshot_id if c.isalnum() or c in "-_")
    if not safe_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid snapshot ID")

    data_dir = _find_data_dir()
    snapshot_file = data_dir / "v1" / "snapshots" / f"{safe_id}.json"
    if not snapshot_file.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snapshot {safe_id} not found",
        )

    content = snapshot_file.read_bytes()
    etag = f'"{hashlib.sha256(content).hexdigest()[:16]}"'

    if if_none_match and if_none_match.strip('"') == etag.strip('"'):
        return Response(
            status_code=status.HTTP_304_NOT_MODIFIED,
            headers={
                "ETag": etag,
                "Cache-Control": "public, max-age=31536000, immutable",
            },
        )

    return Response(
        content=content,
        media_type="application/json",
        headers={
            "ETag": etag,
            "Cache-Control": "public, max-age=31536000, immutable",
            "Access-Control-Allow-Origin": "*",
        },
    )
