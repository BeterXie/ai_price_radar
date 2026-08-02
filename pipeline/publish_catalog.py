from __future__ import annotations

import argparse
import json
import os
import sqlite3
import urllib.parse
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from common import (
    CatalogSnapshot,
    ImportLockUnavailable,
    Offer,
    begin_snapshot,
    ensure_products,
    import_lock,
    session_for,
    upsert_offer,
    utcnow,
)
from connectors import get_connector


UNREVIEWED_DUJIAO_ENV = "AI_PRICE_RADAR_ALLOW_UNREVIEWED_DUJIAO"
PUBLISHABLE_DUJIAO_STATUSES = ("pending_review", "verified")


@dataclass(frozen=True, slots=True)
class SourceSpec:
    connector: str
    source: str


@dataclass(slots=True)
class ImportResult:
    connector: str
    source: str
    total: int = 0
    created: int = 0
    changed: int = 0


@dataclass(slots=True)
class PublishResult:
    snapshot_id: int
    offer_count: int
    imports: list[ImportResult]


class SourceImportError(RuntimeError):
    pass


def _dujiao_origin(value: str) -> str:
    parsed = urllib.parse.urlsplit(value)
    host = (parsed.hostname or "").casefold().rstrip(".")
    if parsed.scheme.casefold() != "https" or not host or parsed.username or parsed.password:
        raise ValueError("Dujiao-Next source must be an HTTPS shop root URL")
    if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise ValueError("Dujiao-Next source must be the shop root URL")
    port = f":{parsed.port}" if parsed.port and parsed.port != 443 else ""
    return f"https://{host}{port}"


def approved_dujiao_sources(review_db: str | Path) -> list[str]:
    path = Path(review_db)
    source_uri = f"{path.resolve().as_uri()}?mode=ro"
    try:
        conn = sqlite3.connect(source_uri, uri=True)
    except sqlite3.Error as exc:
        raise ValueError(f"could not open Dujiao review database: {path}") from exc
    try:
        rows = conn.execute(
            """
            SELECT origin
            FROM dujiao_candidates
            WHERE review_status = 'approved'
              AND api_verified = 1
              AND status IN (?, ?)
            ORDER BY origin
            """,
            PUBLISHABLE_DUJIAO_STATUSES,
        ).fetchall()
    except sqlite3.Error as exc:
        raise ValueError("Dujiao review database is missing a compatible dujiao_candidates table") from exc
    finally:
        conn.close()
    return [_dujiao_origin(str(row[0])) for row in rows]


def dujiao_source_is_approved(source: str, review_db: str | Path) -> bool:
    origin = _dujiao_origin(source)
    return origin in set(approved_dujiao_sources(review_db))


def validate_dujiao_source_access(
    source: str,
    *,
    review_db: str | Path | None,
    allow_unreviewed: bool,
    environ: Mapping[str, str] | None = None,
) -> None:
    if review_db is not None and dujiao_source_is_approved(source, review_db):
        return
    env = environ if environ is not None else os.environ
    gate_enabled = env.get(UNREVIEWED_DUJIAO_ENV, "").strip().casefold() in {"1", "true", "yes"}
    if allow_unreviewed and gate_enabled:
        return
    if allow_unreviewed:
        raise ValueError(f"--allow-unreviewed-source also requires {UNREVIEWED_DUJIAO_ENV}=1")
    raise ValueError("Dujiao-Next source is not approved and API-verified in the review database")


def load_merchant_sources(path: str | Path) -> list[str]:
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    values: Any = document.get("sources") if isinstance(document, dict) else document
    if not isinstance(values, list) or any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValueError("merchant sources must be a JSON string array or an object containing a sources array")
    return [value.strip() for value in values]


def import_source_into_snapshot(
    db: Session,
    *,
    connector: str,
    source: str | Path,
    snapshot_id: int,
    products: dict[str, Any] | None = None,
) -> ImportResult:
    """Import one source without committing or publishing the target snapshot."""
    loader = get_connector(connector)
    products = products or ensure_products(db)
    result = ImportResult(connector=connector, source=str(source))
    current_record: dict[str, Any] | None = None
    try:
        for record in loader(source):
            current_record = record
            result.total += 1
            was_created, was_changed = upsert_offer(db, record, products, snapshot_id)
            result.created += int(was_created)
            result.changed += int(was_changed)
            if result.total % 100 == 0:
                db.flush()
            current_record = None
    except Exception as exc:
        label = current_record.get("product_name") if current_record else None
        detail = f" at record {label!r}" if label else ""
        raise SourceImportError(f"{connector} import failed for {source}{detail}: {exc}") from exc
    return result


def _carry_forward_current_snapshot(db: Session, target_snapshot_id: int) -> None:
    current_id = db.scalar(
        select(CatalogSnapshot.id)
        .where(CatalogSnapshot.published_at.is_not(None))
        .order_by(CatalogSnapshot.id.desc())
        .limit(1)
    )
    if current_id is not None:
        db.execute(update(Offer).where(Offer.snapshot_id == current_id).values(snapshot_id=target_snapshot_id))


def publish_sources(
    db: Session,
    sources: Sequence[SourceSpec],
    *,
    source_label: str = "multi-source",
    carry_forward_current: bool = False,
    dry_run: bool = False,
) -> PublishResult:
    """Publish all sources in one transaction; any failure restores the current catalog."""
    if not sources:
        raise ValueError("at least one catalog source is required")
    try:
        with import_lock(db):
            products = ensure_products(db)
            snapshot = begin_snapshot(db, source_label)
            if carry_forward_current:
                _carry_forward_current_snapshot(db, snapshot.id)
            imports = [
                import_source_into_snapshot(
                    db,
                    connector=spec.connector,
                    source=spec.source,
                    snapshot_id=snapshot.id,
                    products=products,
                )
                for spec in sources
            ]
            snapshot.offer_count = int(
                db.scalar(select(func.count(Offer.id)).where(Offer.snapshot_id == snapshot.id)) or 0
            )
            result = PublishResult(snapshot_id=snapshot.id, offer_count=snapshot.offer_count, imports=imports)
            if dry_run:
                db.rollback()
            else:
                snapshot.published_at = utcnow()
                db.commit()
            return result
    except Exception:
        db.rollback()
        raise


def _build_sources(args: argparse.Namespace) -> list[SourceSpec]:
    sources: list[SourceSpec] = []
    if args.ldxp_db:
        sources.append(SourceSpec("ldxp", str(args.ldxp_db)))
    if args.dujiao_db:
        sources.extend(SourceSpec("dujiao-next", origin) for origin in approved_dujiao_sources(args.dujiao_db))
    if args.merchant_sources:
        sources.extend(SourceSpec("merchant-json", source) for source in load_merchant_sources(args.merchant_sources))
    return sources


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Atomically publish one catalog snapshot from all configured and approved sources"
    )
    parser.add_argument("--ldxp-db", type=Path, help="LDXP crawler SQLite database")
    parser.add_argument(
        "--dujiao-db",
        type=Path,
        help="Discovery SQLite database; only approved, currently API-verified candidates are imported",
    )
    parser.add_argument("--merchant-sources", type=Path, help="JSON list of configured merchant feed paths or URLs")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", ""))
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")
    for path, label in (
        (args.ldxp_db, "LDXP database"),
        (args.dujiao_db, "Dujiao review database"),
        (args.merchant_sources, "merchant sources file"),
    ):
        if path and not path.is_file():
            parser.error(f"{label} not found: {path}")
    try:
        sources = _build_sources(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    if not sources:
        parser.error("no importable sources were configured")

    db = session_for(args.database_url)
    try:
        result = publish_sources(db, sources)
    except ImportLockUnavailable as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 3
    except Exception as exc:
        print(json.dumps({"error": str(exc), "published": False}, ensure_ascii=False))
        return 2
    finally:
        db.close()
    print(json.dumps({
        "snapshot_id": result.snapshot_id,
        "offer_count": result.offer_count,
        "published": True,
        "imports": [asdict(item) for item in result.imports],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
