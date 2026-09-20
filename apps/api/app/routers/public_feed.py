from __future__ import annotations

import os
import re
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException, Response, status
from fastapi.responses import FileResponse

router = APIRouter(tags=["public-feed"])

# Set PUBLIC_DATA_DIR to the shared export directory in containers. The API image
# does not include apps/web, so the host-path probes below only help for local runs.
PUBLIC_DATA_DIR_ENV = "PUBLIC_DATA_DIR"


def _get_candidate_data_dirs() -> list[Path]:
    dirs: list[Path] = []
    configured = os.getenv(PUBLIC_DATA_DIR_ENV, "").strip()
    if configured:
        dirs.append(Path(configured))
    dirs.extend([
        Path("/workspace/apps/web/public/data"),
        Path("/opt/ai-price-radar-v3/apps/web/public/data"),
        Path("./data"),
    ])
    cur = Path(__file__).resolve()
    for p in cur.parents:
        dirs.append(p / "apps" / "web" / "public" / "data")
        dirs.append(p / "web" / "public" / "data")
        dirs.append(p / "data")
    return dirs


def _find_data_dir() -> Path:
    configured = os.getenv(PUBLIC_DATA_DIR_ENV, "").strip()
    if configured:
        return Path(configured)
    for candidate in _get_candidate_data_dirs():
        if candidate.is_dir():
            return candidate
    return Path("./data")


def _file_etag(path: Path) -> tuple[str, os.stat_result]:
    stat_result = path.stat()
    return f'W/"{stat_result.st_mtime_ns:x}-{stat_result.st_size:x}"', stat_result


def _etag_matches(header_value: str | None, etag: str) -> bool:
    if not header_value:
        return False
    normalized = etag.removeprefix("W/")
    return any(
        candidate.strip().removeprefix("W/") in {normalized, "*"}
        for candidate in header_value.split(",")
    )


def _serve_feed_file(path: Path, if_none_match: str | None, cache_control: str) -> Response:
    etag, stat_result = _file_etag(path)
    headers = {
        "ETag": etag,
        "Cache-Control": cache_control,
        "Access-Control-Allow-Origin": "*",
    }
    if _etag_matches(if_none_match, etag):
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)
    return FileResponse(
        path,
        media_type="application/json",
        headers=headers,
        stat_result=stat_result,
    )


@router.get("/data/latest.json")
def get_latest_feed(if_none_match: str | None = Header(None)) -> Response:
    data_dir = _find_data_dir()
    latest_file = data_dir / "latest.json"
    if not latest_file.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Latest snapshot feed has not been generated yet",
        )

    return _serve_feed_file(
        latest_file,
        if_none_match,
        "public, max-age=60, stale-while-revalidate=300",
    )


@router.get("/data/v1/snapshots/{snapshot_id}.json")
def get_snapshot_feed(snapshot_id: str, if_none_match: str | None = Header(None)) -> Response:
    if re.fullmatch(r"[A-Za-z0-9_-]{1,128}", snapshot_id) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid snapshot ID")

    data_dir = _find_data_dir()
    snapshot_file = data_dir / "v1" / "snapshots" / f"{snapshot_id}.json"
    if not snapshot_file.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snapshot {snapshot_id} not found",
        )
    return _serve_feed_file(snapshot_file, if_none_match, "public, max-age=31536000, immutable")
