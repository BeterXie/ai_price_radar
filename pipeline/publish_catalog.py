from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sqlite3
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)
from typing import Any, Mapping, Sequence

from sqlalchemy import func, inspect, select, text, update
from sqlalchemy.orm import Session

from common import (
    CatalogSnapshot,
    ImportLockUnavailable,
    Offer,
    Shop,
    begin_snapshot,
    ensure_products,
    import_lock,
    session_for,
    upsert_offer,
    utcnow,
)
from connectors import get_connector
from connectors.ldxp import load_records as load_ldxp_records
from intake_bridge import IntakeBridge
from ldxp_intake import collect_intake_metadata, onboard_published_intakes, published_offer_counts


UNREVIEWED_DUJIAO_ENV = "AI_PRICE_RADAR_ALLOW_UNREVIEWED_DUJIAO"
PUBLISHABLE_DUJIAO_STATUSES = ("pending_review", "verified")
STALE_OFFER_HOURS_ENV = "STALE_OFFER_HOURS"
DEFAULT_STALE_OFFER_HOURS = 72
MAX_STALE_OFFER_HOURS = 24 * 30


@dataclass(frozen=True, slots=True)
class SourceSpec:
    connector: str
    source: str
    intake_ids: tuple[int, ...] = ()


@dataclass(slots=True)
class ImportResult:
    connector: str
    source: str
    total: int = 0
    raw_record_count: int = 0
    classified_offer_count: int = 0
    public_offer_count: int = 0
    created: int = 0
    changed: int = 0
    pruned: int = 0
    offer_ids: set[int] = field(default_factory=set)
    shop_tokens: set[str] = field(default_factory=set)
    new_shop_tokens: set[str] = field(default_factory=set)

    def to_dict(self) -> dict[str, int | str]:
        return {
            "connector": self.connector,
            "source": self.source,
            "total": self.total,
            "raw_record_count": self.raw_record_count,
            "classified_offer_count": self.classified_offer_count,
            "public_offer_count": self.public_offer_count,
            "created": self.created,
            "changed": self.changed,
            "pruned": self.pruned,
        }


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


def approved_intake_sources(db: Session) -> list[SourceSpec]:
    if not inspect(db.get_bind()).has_table("source_intakes"):
        return []
    rows = db.execute(text(
        "SELECT id, source_type, source_url FROM source_intakes "
        "WHERE status IN ('approved', 'published') "
        "AND source_type IN ('merchant_json', 'woocommerce', '16688', 'schema_org') "
        "AND detected_platform=source_type "
        "ORDER BY id"
    )).mappings()
    connector_by_type = {
        "dujiao_next": "dujiao-next",
        "merchant_json": "merchant-json",
        "woocommerce": "woocommerce-store",
        "16688": "16688",
        "schema_org": "schema-org",
    }
    return [
        SourceSpec(connector_by_type[row["source_type"]], row["source_url"], (int(row["id"]),))
        for row in rows
    ]


def merge_sources(sources: Sequence[SourceSpec]) -> list[SourceSpec]:
    merged: dict[tuple[str, str], SourceSpec] = {}
    for spec in sources:
        key = (spec.connector, spec.source)
        previous = merged.get(key)
        intake_ids = tuple(dict.fromkeys([*(previous.intake_ids if previous else ()), *spec.intake_ids]))
        merged[key] = SourceSpec(spec.connector, spec.source, intake_ids)
    return list(merged.values())


def public_offer_count(
    db: Session,
    *,
    snapshot_id: int,
    offer_ids: set[int],
    now: datetime | None = None,
) -> int:
    """Count imported offers using the same visibility and freshness rules as the public catalog."""
    if not offer_ids:
        return 0
    try:
        stale_offer_hours = int(os.environ.get(STALE_OFFER_HOURS_ENV, DEFAULT_STALE_OFFER_HOURS))
    except ValueError as exc:
        raise ValueError(f"{STALE_OFFER_HOURS_ENV} must be an integer") from exc
    if not 1 <= stale_offer_hours <= MAX_STALE_OFFER_HOURS:
        raise ValueError(
            f"{STALE_OFFER_HOURS_ENV} must be between 1 and {MAX_STALE_OFFER_HOURS}"
        )
    cutoff = (now or utcnow()) - timedelta(hours=stale_offer_hours)
    return int(db.scalar(
        select(func.count(Offer.id))
        .join(Shop, Shop.id == Offer.shop_id)
        .where(
            Offer.snapshot_id == snapshot_id,
            Offer.id.in_(offer_ids),
            Offer.active.is_(True),
            Offer.approved.is_(True),
            Offer.product_id.is_not(None),
            Shop.is_visible.is_(True),
            Offer.observed_at >= cutoff,
        )
    ) or 0)


def onboard_validated_ldxp_intakes(
    db: Session,
    *,
    snapshot_id: int,
    intake_tokens: dict[int, set[str]],
    intake_attempts: dict[int, int],
    api_url: str,
    worker_key: str,
    bridge_factory=IntakeBridge,
) -> list[dict[str, object]]:
    inspector = inspect(db.get_bind())
    if (
        not intake_tokens
        or not inspector.has_table("source_intakes")
        or "attempt_count" not in {column["name"] for column in inspector.get_columns("source_intakes")}
    ):
        return []
    public_counts = published_offer_counts(db, snapshot_id, intake_tokens)
    if not public_counts:
        return []
    current_attempts = {
        int(row["id"]): int(row["attempt_count"])
        for row in db.execute(text(
            "SELECT id, attempt_count FROM source_intakes "
            "WHERE source_type='ldxp' AND status='validated'"
        )).mappings()
    }
    eligible_counts = {
        intake_id: product_count
        for intake_id, product_count in public_counts.items()
        if intake_attempts.get(intake_id) == current_attempts.get(intake_id)
    }
    return onboard_published_intakes(
        eligible_counts,
        intake_attempts,
        api_url=api_url,
        worker_key=worker_key,
        bridge_factory=bridge_factory,
    )


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
    offer_ids: set[int] = set()
    shop_tokens: set[str] = set()
    new_shop_tokens: set[str] = set()
    current_record: dict[str, Any] | None = None
    try:
        for record in loader(source):
            current_record = record
            result.total += 1
            result.raw_record_count += 1
            was_created, was_changed = upsert_offer(
                db,
                record,
                products,
                snapshot_id,
                collected_offer_ids=offer_ids,
                collected_new_shop_tokens=new_shop_tokens,
            )
            if token := str(record.get("token") or "").strip():
                shop_tokens.add(token)
            result.created += int(was_created)
            result.changed += int(was_changed)
            if result.total % 100 == 0:
                db.flush()
            current_record = None
    except Exception as exc:
        label = current_record.get("product_name") if current_record else None
        detail = f" at record {label!r}" if label else ""
        raise SourceImportError(f"{connector} import failed for {source}{detail}: {exc}") from exc
    db.flush()
    if offer_ids:
        source_offers = (
            Offer.snapshot_id == snapshot_id,
            Offer.id.in_(offer_ids),
        )
        result.classified_offer_count = int(db.scalar(
            select(func.count(Offer.id))
            .join(Shop, Shop.id == Offer.shop_id)
            .where(*source_offers, Offer.product_id.is_not(None))
        ) or 0)
        result.public_offer_count = public_offer_count(
            db,
            snapshot_id=snapshot_id,
            offer_ids=offer_ids,
        )
    result.offer_ids = offer_ids
    result.shop_tokens = shop_tokens
    result.new_shop_tokens = new_shop_tokens
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


def _prune_stale_offers(
    db: Session,
    *,
    snapshot_id: int,
    valid_offer_ids: set[int],
) -> int:
    """Prune offers belonging to touched shops that are no longer present in the updated source."""
    if not valid_offer_ids:
        return 0

    touched_shop_ids = set(
        db.scalars(
            select(Offer.shop_id)
            .where(Offer.id.in_(valid_offer_ids))
            .distinct()
        ).all()
    )
    if not touched_shop_ids:
        return 0

    current_ids = set(
        db.scalars(
            select(Offer.id)
            .where(
                Offer.snapshot_id == snapshot_id,
                Offer.shop_id.in_(touched_shop_ids),
            )
        ).all()
    )
    stale_ids = current_ids - valid_offer_ids
    if not stale_ids:
        return 0

    db.execute(
        update(Offer)
        .where(Offer.id.in_(stale_ids), Offer.snapshot_id == snapshot_id)
        .values(snapshot_id=None, stock_status="unavailable")
    )
    return len(stale_ids)


def _looks_like_url(value: str) -> bool:
    """Detect applicant input that is really a host or URL, not a shop name."""
    text = str(value or "").strip()
    if not text or any(character.isspace() for character in text):
        return False
    if "://" in text:
        return True
    host = text.split("/", 1)[0]
    return re.fullmatch(r"[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?::\d+)?", host) is not None


def _shop_row(db: Session, clause: str, params: Mapping[str, Any], *, unique: bool = False) -> dict[str, Any] | None:
    rows = db.execute(text(
        f"SELECT token, name, source_url FROM shops WHERE {clause} ORDER BY id LIMIT 2"
    ), dict(params)).mappings().all()
    if not rows or (unique and len(rows) > 1):
        return None
    return dict(rows[0])


def resolve_intake_shop(
    db: Session,
    *,
    source_url: str,
    source_key: str,
    source_type: str = "",
    preferred_token: str | None = None,
) -> dict[str, Any] | None:
    """Find the shop a source intake actually produced.

    An intake keeps the address the applicant submitted, which may be a goods page
    or a feed URL rather than the shop's own page. Every lookup must therefore prove
    the identity instead of assuming ``source_key`` is a shop token; callers use the
    returned token for public links and otherwise omit them.
    """
    # Reflect through the session's own connection: asking a separately checked-out
    # pooled connection for schema metadata can roll back the open transaction.
    inspector = inspect(db.connection())
    if not inspector.has_table("shops"):
        return None
    if preferred_token:
        if row := _shop_row(db, "token = :token", {"token": preferred_token}):
            return row
    for value in (source_url, source_key):
        if value:
            if row := _shop_row(db, "source_url = :value", {"value": value}):
                return row
    if source_key:
        if row := _shop_row(db, "lower(token) = lower(:token)", {"token": source_key}):
            return row
    goods_key = _goods_product_key(source_url or source_key, source_type)
    if goods_key and inspector.has_table("raw_products"):
        rows = db.execute(text(
            "SELECT s.token, s.name, s.source_url FROM raw_products rp "
            "JOIN shops s ON s.id = rp.shop_id "
            "WHERE rp.source_product_key = :key ORDER BY rp.id LIMIT 2"
        ), {"key": goods_key}).mappings().all()
        if len(rows) == 1:
            return dict(rows[0])
    # Last resort for single-origin sources (merchant feeds, WooCommerce, Schema.org):
    # the shop page is the origin of the submitted address, never a bare host shared
    # by unrelated shops.
    origin = _source_origin(source_url or source_key)
    if origin:
        return _shop_row(db, "source_url = :origin", {"origin": origin}, unique=True)
    return None


def _source_origin(value: str) -> str:
    parsed = urllib.parse.urlsplit(str(value or "").strip())
    if not parsed.scheme or not parsed.hostname:
        return ""
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))


def _normalize_url(value: str) -> str:
    text = str(value or "").strip().rstrip("/")
    return text.casefold()


def _shop_has_product_url(db: Session, shop_token: str, url: str) -> bool:
    """True when ``url`` is a product page already imported for the given shop."""
    if not url or not inspect(db.connection()).has_table("raw_products"):
        return False
    return db.execute(text(
        "SELECT 1 FROM raw_products rp JOIN shops s ON s.id = rp.shop_id "
        "WHERE s.token = :token AND lower(rp.source_url) = lower(:url) LIMIT 1"
    ), {"token": shop_token, "url": url}).scalar_one_or_none() is not None


def _goods_product_key(value: str, source_type: str) -> str:
    """Map a single goods page (``/goods/{code}``) back to the imported product key."""
    platform = str(source_type or "").strip().casefold().replace("-", "_")
    if not platform:
        return ""
    parsed = urllib.parse.urlsplit(str(value or "").strip())
    match = re.fullmatch(r"/goods/([A-Za-z0-9._~-]+)/?", parsed.path)
    if match is None:
        return ""
    return f"{platform}:{urllib.parse.unquote(match.group(1)).strip()}"


def _insert_outbox_row(db: Session, values: Mapping[str, Any], *, dedupe_key: str) -> None:
    columns = (
        "(event_type, recipient, subject, text_body, status, attempt_count, "
        "next_attempt_at, last_error, dedupe_key, created_at)"
    )
    placeholders = "(:event_type, :recipient, :subject, :text_body, 'pending', 0, :now, '', :dedupe_key, :now)"
    conflict = " ON CONFLICT (dedupe_key) DO NOTHING" if db.get_bind().dialect.name == "postgresql" else ""
    db.execute(text(
        f"INSERT INTO notification_outbox {columns} VALUES {placeholders}{conflict}"
    ), dict(values, dedupe_key=dedupe_key))


def enqueue_published_intake_notifications(
    db: Session,
    *,
    intake_id: int,
    intake_status: str,
    product_count: int,
    published_at: datetime,
    preferred_shop_token: str | None = None,
    new_shop_tokens: set[str] | None = None,
) -> None:
    conn = db.connection()
    inspector = inspect(conn)
    if not inspector.has_table("notification_outbox") or not inspector.has_table("source_intakes"):
        return

    intake_columns = {col["name"] for col in inspector.get_columns("source_intakes")}
    if "contact_email" not in intake_columns:
        return

    row = db.execute(text(
        "SELECT id, shop_name, source_url, source_key, source_type, contact_email "
        "FROM source_intakes WHERE id = :intake_id"
    ), {"intake_id": intake_id}).mappings().one_or_none()

    if not row:
        return
    contact_email = str(row.get("contact_email") or "").strip()
    if not contact_email:
        return

    shop_name = str(row.get("shop_name") or "").strip()
    source_url = str(row.get("source_url") or "").strip()
    source_key = str(row.get("source_key") or "").strip()
    source_type = str(row.get("source_type") or "").strip()
    shop = resolve_intake_shop(
        db,
        source_url=source_url,
        source_key=source_key,
        source_type=source_type,
        preferred_token=preferred_shop_token,
    )
    shop_token = str(shop.get("token") or "").strip() if shop else ""
    display_name = shop_name
    if shop and (not display_name or _looks_like_url(display_name)):
        display_name = str(shop.get("name") or "").strip()
    display_url = str(shop.get("source_url") or "").strip() if shop else ""
    display_url = display_url or source_url
    # An applicant may submit one product page of a shop the catalog already carries.
    # Only an existing product of that shop proves the intent, so a merchant feed or a
    # refreshed shop page still receives the onboarding mail instead of a rule notice.
    shop_is_new = bool(shop_token) and shop_token in (new_shop_tokens or set())
    submitted_url = source_url or source_key
    is_product_request = (
        not shop_is_new
        and bool(shop_token)
        and _normalize_url(submitted_url) != _normalize_url(display_url)
        and _shop_has_product_url(db, shop_token, submitted_url)
    )
    site_base = os.getenv("PUBLIC_SITE_URL", "https://ai.pricememo.cn").rstrip("/")
    shop_page = (
        f"{site_base}/shops/{urllib.parse.quote(shop_token, safe='')}" if shop_token else ""
    )

    if intake_status == "published":
        if is_product_request:
            event_type = "shop_intake.goods_added"
        else:
            event_type = "shop_intake.onboarded"
        dedupe_key = f"source-intake:{intake_id}:{event_type}"
        already = db.execute(text(
            "SELECT 1 FROM notification_outbox WHERE dedupe_key = :key"
        ), {"key": dedupe_key}).scalar_one_or_none()
        if already:
            return

        if is_product_request:
            subject = "店铺已收录，新增商品无需重新申请"
            lines = [
                f"你提交的收录申请（#{intake_id}）已完成处理。",
                f"所属店铺：{display_name or '未填写'}",
                f"店铺地址：{display_url}",
                f"本次提交地址：{submitted_url}",
                "",
                "该地址所属店铺已在收录列表中，无需重复申请收录：",
                "1. 店铺收录后，系统会自动扫描并同步该店铺后续新增的商品；",
                "2. 已在收录列表中的店铺，新增商品无需再次提交收录申请；",
                "3. 商品价格与库存会随自动扫描持续更新，无需人工干预。",
            ]
            if shop_page:
                lines.append(f"店铺收录页面：{shop_page}")
        else:
            subject = "店铺已正式收录"
            lines = [
                f"你的店铺收录申请（#{intake_id}）已完成验证并发布。",
                f"店铺名称：{display_name or '未填写'}",
                f"店铺地址：{display_url}",
                f"已发布商品数：{product_count}。",
            ]
            if shop_page:
                lines.append(f"本站收录页面：{shop_page}")
            if not shop_is_new:
                lines.append("系统会持续自动扫描并更新该店铺商品，无需重复提交收录申请。")
        body = "\n".join(lines)
    elif intake_status == "no_products":
        event_type = "shop_intake.no_products"
        dedupe_key = f"source-intake:{intake_id}:shop_intake.no_products"

        already = db.execute(text(
            "SELECT 1 FROM notification_outbox WHERE dedupe_key = :key"
        ), {"key": dedupe_key}).scalar_one_or_none()
        if already:
            return

        subject = "店铺验证完成，但暂未发现目标商品"
        body = (
            f"你的店铺收录申请（#{intake_id}）已完成读取，但暂未发现目录范围内商品。\n"
            f"店铺名称：{display_name or '未填写'}\n"
            f"店铺地址：{display_url}\n"
            "管理员可以重新验证，或补充公开商品后再次提交。"
        )
    else:
        return

    _insert_outbox_row(db, {
        "event_type": event_type,
        "recipient": contact_email,
        "subject": subject,
        "text_body": body,
        "now": published_at,
    }, dedupe_key=dedupe_key)


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
            imports: list[ImportResult] = []
            published_at = utcnow()
            for spec in sources:
                imported = import_source_into_snapshot(
                    db,
                    connector=spec.connector,
                    source=spec.source,
                    snapshot_id=snapshot.id,
                    products=products,
                )
                if carry_forward_current and imported.offer_ids:
                    imported.pruned = _prune_stale_offers(
                        db,
                        snapshot_id=snapshot.id,
                        valid_offer_ids=imported.offer_ids,
                    )
                imports.append(imported)
                for intake_id in spec.intake_ids:
                    intake_status = "published" if imported.public_offer_count > 0 else "no_products"
                    db.execute(text(
                        "UPDATE source_intakes "
                        "SET status=:status, product_count=:product_count, "
                        "finished_at=:published_at, updated_at=:published_at "
                        "WHERE id=:intake_id AND status IN ('approved', 'published')"
                    ), {
                        "intake_id": intake_id,
                        "status": intake_status,
                        "product_count": imported.public_offer_count,
                        "published_at": published_at,
                    })
                    enqueue_published_intake_notifications(
                        db,
                        intake_id=intake_id,
                        intake_status=intake_status,
                        product_count=imported.public_offer_count,
                        published_at=published_at,
                        preferred_shop_token=(
                            next(iter(imported.shop_tokens))
                            if len(imported.shop_tokens) == 1
                            else None
                        ),
                        new_shop_tokens=imported.new_shop_tokens,
                    )
            snapshot.offer_count = int(
                db.scalar(select(func.count(Offer.id)).where(Offer.snapshot_id == snapshot.id)) or 0
            )
            result = PublishResult(snapshot_id=snapshot.id, offer_count=snapshot.offer_count, imports=imports)
            if dry_run:
                db.rollback()
            else:
                snapshot.published_at = published_at
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
    db = session_for(args.database_url)
    try:
        intake_tokens: dict[int, set[str]] = {}
        intake_attempts: dict[int, int] = {}
        if args.ldxp_db:
            intake_tokens, intake_attempts = collect_intake_metadata(load_ldxp_records(args.ldxp_db))
        sources = merge_sources([*sources, *approved_intake_sources(db)])
        if not sources:
            parser.error("no importable sources were configured or approved")
        result = publish_sources(db, sources)
        onboarding_errors = onboard_validated_ldxp_intakes(
            db,
            snapshot_id=result.snapshot_id,
            intake_tokens=intake_tokens,
            intake_attempts=intake_attempts,
            api_url=os.getenv("INTAKE_API_URL", ""),
            worker_key=os.getenv("INTAKE_WORKER_KEY", ""),
        )
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
        "onboarding_failed": len(onboarding_errors),
        "imports": [item.to_dict() for item in result.imports],
    }, ensure_ascii=False))
    for error in onboarding_errors:
        print(json.dumps({**error, "published_data_remains_validated": True}, ensure_ascii=False))
    return 0 if not onboarding_errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
