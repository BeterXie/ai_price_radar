from __future__ import annotations

import json
import logging
import os
import statistics
import tempfile
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from common import CatalogSnapshot, Offer, Product, RawProduct, Shop, session_for

logger = logging.getLogger(__name__)

DEFAULT_OUTPUT_DIR = Path(
    os.getenv("PUBLIC_DATA_DIR", "").strip()
    or (Path(__file__).resolve().parent.parent / "apps" / "web" / "public" / "data")
)
DEFAULT_PUBLIC_BASE_URL = os.getenv("PUBLIC_SITE_URL", "https://ai.pricememo.cn")

# Mirrors apps/api/app/services/source_platform.py so exported JSON never
# contains offers the public catalog hides.
DISABLED_SOURCE_PLATFORMS: set[str] = {"dujiao_next"}
# Mirrors services/pricing.py: prices below this absolute floor are not trusted.
MIN_TRUSTED_PRICE_CNY = Decimal("1.00")
DEFAULT_STALE_OFFER_HOURS = 72


def _as_utc(value: datetime | None) -> datetime | None:
    """Normalize naive datetimes (SQLite returns naive even for tz-aware columns)."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _fresh_cutoff(reference_time: datetime) -> datetime:
    """Fixed staleness cutoff mirroring the public catalog."""
    hours = os.getenv("STALE_OFFER_HOURS", str(DEFAULT_STALE_OFFER_HOURS)).strip()
    try:
        parsed_hours = float(hours)
    except ValueError:
        parsed_hours = float(DEFAULT_STALE_OFFER_HOURS)
    return reference_time - timedelta(hours=parsed_hours)

OFFICIAL_REFERENCES: dict[str, dict[str, Any]] = {
    "chatgpt-plus": {
        "provider": "OpenAI",
        "plan": "ChatGPT Plus",
        "price": "20.00",
        "currency": "USD",
        "billing_period": "month",
        "url": "https://help.openai.com/en/articles/6950777-what-is-chatgpt-plus",
        "checked_at": "2026-07-29",
        "note": "美国网页公开月价；OpenAI 支持多币种与本地化结算，税费和应用商店价格可能不同。",
    },
    "claude-pro": {
        "provider": "Anthropic",
        "plan": "Claude Pro",
        "price": "20.00",
        "currency": "USD",
        "billing_period": "month",
        "url": "https://support.anthropic.com/en/articles/8325610-how-much-does-claude-pro-cost",
        "checked_at": "2026-07-29",
        "note": "美国公开月价；部分地区使用本地货币，税费和年付折扣可能不同。",
    },
    "gemini-advanced": {
        "provider": "Google",
        "plan": "Google AI Pro",
        "price": "19.99",
        "currency": "USD",
        "billing_period": "month",
        "url": "https://one.google.com/about/plans",
        "checked_at": "2026-07-29",
        "note": "美国公开月价；Google AI 方案名称、存储权益、促销和地区可用性可能变化。",
    },
    "grok-super": {
        "provider": "xAI",
        "plan": "SuperGrok",
        "price": "30.00",
        "currency": "USD",
        "billing_period": "month",
        "url": "https://x.ai/pricing",
        "checked_at": "2026-07-29",
        "note": "美国公开月价；地区、税费、支付渠道、促销和产品权益可能变化。",
    },
    "x-premium-basic": {
        "provider": "X",
        "plan": "X Premium Basic",
        "price": "3.00",
        "currency": "USD",
        "billing_period": "month",
        "url": "https://help.x.com/en/using-x/x-premium",
        "checked_at": "2026-07-29",
        "note": "美国网页起始月价；地区、税费、支付渠道和客户端价格可能不同。",
    },
    "x-premium": {
        "provider": "X",
        "plan": "X Premium",
        "price": "8.00",
        "currency": "USD",
        "billing_period": "month",
        "url": "https://help.x.com/en/using-x/x-premium",
        "checked_at": "2026-07-29",
        "note": "美国网页起始月价；地区、税费、支付渠道和客户端价格可能不同。",
    },
    "x-premium-plus": {
        "provider": "X",
        "plan": "X Premium+",
        "price": "40.00",
        "currency": "USD",
        "billing_period": "month",
        "url": "https://help.x.com/en/using-x/x-premium",
        "checked_at": "2026-07-29",
        "note": "美国网页起始月价；地区、税费、支付渠道和客户端价格可能不同。",
    },
}


def _calc_data_quality(total_offers: int, source_count: int, comparable_count: int, trusted_count: int, latest_dt: datetime | None) -> tuple[int, str]:
    if total_offers == 0:
        return 0, "数据不足"
    trusted_ratio = trusted_count / comparable_count if comparable_count else 0
    freshness = 0
    latest_utc = _as_utc(latest_dt)
    if latest_utc is not None:
        now = datetime.now(timezone.utc)
        age_hours = max(0.0, (now - latest_utc).total_seconds() / 3600.0)
        freshness = 30 if age_hours <= 6 else 22 if age_hours <= 24 else 12 if age_hours <= 72 else 0
    score = round(45 * trusted_ratio + min(25, source_count * 5) + freshness)
    score = max(0, min(100, score))
    label = "充足" if score >= 80 else "一般" if score >= 55 else "有限"
    return score, label


def export_public_snapshot(
    db: Session,
    snapshot_id: int | None = None,
    output_dir: Path | str | None = None,
    public_base_url: str | None = None,
    allow_historical: bool = False,
) -> dict[str, Any]:
    """Export public immutable snapshot JSON and update latest.json pointer.

    Only the current published snapshot may update the latest.json pointer, so a
    re-export of a historical archive cannot roll the public feed backwards.
    """
    target_dir = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    base_url = (public_base_url or DEFAULT_PUBLIC_BASE_URL).rstrip("/")

    snapshots_dir = target_dir / "v1" / "snapshots"
    snapshots_dir.mkdir(parents=True, exist_ok=True)

    if snapshot_id is not None:
        snapshot = db.scalar(select(CatalogSnapshot).where(CatalogSnapshot.id == snapshot_id))
    else:
        snapshot = db.scalar(
            select(CatalogSnapshot)
            .where(CatalogSnapshot.published_at.is_not(None))
            .order_by(CatalogSnapshot.id.desc())
            .limit(1)
        )
    if not snapshot:
        raise ValueError(f"CatalogSnapshot {snapshot_id or 'latest'} not found")
    if snapshot.published_at is None:
        raise ValueError(f"CatalogSnapshot {snapshot.id} is not published; refusing to export it publicly")
    snapshot_id = snapshot.id

    current_snapshot = db.scalar(
        select(CatalogSnapshot)
        .where(CatalogSnapshot.published_at.is_not(None))
        .order_by(CatalogSnapshot.id.desc())
        .limit(1)
    )
    is_current_snapshot = bool(current_snapshot and current_snapshot.id == snapshot_id)
    if snapshot_id and not is_current_snapshot and not allow_historical:
        raise ValueError(
            f"CatalogSnapshot {snapshot_id} is not the current published snapshot "
            f"(current: {current_snapshot.id if current_snapshot else 'none'}); "
            "pass allow_historical=True to archive-export without touching latest.json"
        )

    products = db.scalars(
        select(Product).where(Product.is_visible == True).order_by(Product.id)
    ).all()

    now_utc = datetime.now(timezone.utc)
    published_dt = _as_utc(snapshot.published_at or snapshot.created_at) or now_utc
    age_hours = (now_utc - published_dt).total_seconds() / 3600.0
    is_stale = age_hours > 2.0

    product_snapshots: list[dict[str, Any]] = []

    total_offers_count = 0
    total_in_stock_count = 0
    total_comparable_count = 0
    total_trusted_count = 0

    for product in products:
        stmt = (
            select(Offer, Shop, RawProduct)
            .join(Shop, Offer.shop_id == Shop.id)
            .join(RawProduct, Offer.raw_product_id == RawProduct.id)
            .where(
                and_(
                    Offer.snapshot_id == snapshot_id,
                    Offer.product_id == product.id,
                    Offer.active == True,
                    Offer.approved == True,
                    Shop.is_visible == True,
                    Shop.status != "closed",
                    # Keep parity with the public catalog: hidden offers must not
                    # reappear through the exported feed.
                    or_(Offer.hidden_reason.is_(None), func.trim(Offer.hidden_reason) == ""),
                )
            )
        )
        if DISABLED_SOURCE_PLATFORMS:
            stmt = stmt.where(
                or_(Shop.platform.is_(None), Shop.platform.notin_(DISABLED_SOURCE_PLATFORMS))
        )
        stmt = stmt.where(Offer.observed_at >= _fresh_cutoff(published_dt))
        rows = db.execute(stmt).all()
        if not rows:
            continue

        offer_count = len(rows)
        total_offers_count += offer_count

        in_stock_rows = [
            r for r in rows
            if r[0].stock_status == "in_stock" and r[0].price is not None and r[0].price > 0
        ]
        in_stock_count = len(in_stock_rows)
        total_in_stock_count += in_stock_count

        comparable_count = sum(1 for r in rows if r[0].is_comparable)
        total_comparable_count += comparable_count

        # Price statistics remain CNY-only even though inventory and comparable
        # counts describe all public offers, matching the API card contract.
        cny_in_stock_rows = [
            r for r in in_stock_rows if (r[0].currency or "CNY").upper() == "CNY"
        ]
        comparable_rows = [r for r in cny_in_stock_rows if r[0].is_comparable]

        # Compute medians by delivery_type
        delivery_prices: dict[str, list[float]] = defaultdict(list)
        for r in comparable_rows:
            delivery_prices[r[0].delivery_type or "unknown"].append(float(r[0].price))
        delivery_medians = {
            dt: statistics.median(p_list) for dt, p_list in delivery_prices.items() if p_list
        }

        # Trusted offers (comparable, in_stock, price >= 0.4 * median AND >= 1 CNY floor)
        trusted_rows = []
        for r in comparable_rows:
            p_val = float(r[0].price)
            med = delivery_medians.get(r[0].delivery_type or "unknown")
            if (med is None or p_val >= (med * 0.4)) and r[0].price >= MIN_TRUSTED_PRICE_CNY:
                trusted_rows.append(r)
        trusted_count = len(trusted_rows)
        total_trusted_count += trusted_count
        trusted_offer_ids = {r[0].id for r in trusted_rows}

        # Prices
        trusted_prices = [float(r[0].price) for r in trusted_rows]
        lowest_price = min(trusted_prices) if trusted_prices else None
        lowest_price_str = f"{lowest_price:.2f}" if lowest_price is not None else None

        in_stock_prices = [float(r[0].price) for r in cny_in_stock_rows]
        related_lowest_price = min(in_stock_prices) if in_stock_prices else None
        related_lowest_price_str = f"{related_lowest_price:.2f}" if related_lowest_price is not None else None

        comparable_prices = [float(r[0].price) for r in comparable_rows]
        median_price_val = statistics.median(comparable_prices) if comparable_prices else None
        median_price_str = f"{median_price_val:.2f}" if median_price_val is not None else None

        # Data quality
        source_count = len({r[1].id for r in rows})
        latest_obs = max((r[0].observed_at for r in rows), default=None)
        score, label = _calc_data_quality(
            offer_count,
            source_count,
            len(comparable_rows),
            trusted_count,
            latest_obs,
        )

        # Tags
        all_tags = sorted({t for r in rows for t in (r[0].tags or [])})[:8]

        # Official reference
        official_ref = OFFICIAL_REFERENCES.get(product.slug)

        def offer_sort_key(item):
            offer, shop, _ = item
            is_stock = 0 if offer.stock_status == "in_stock" else 1
            is_comp = 0 if offer.is_comparable else 1
            price_val = float(offer.price) if offer.price is not None else 999999.0
            return (is_stock, is_comp, price_val)

        sorted_rows = sorted(rows, key=offer_sort_key)
        top_5_rows = sorted_rows[:5]

        top_5_offers = []
        for offer, shop, raw in top_5_rows:
            # Reuse the same trusted set the aggregate metrics were computed from
            # so summary and detail can never disagree.
            is_trusted = offer.id in trusted_offer_ids
            top_5_offers.append({
                "id": offer.id,
                "shop_token": shop.token,
                "shop_name": shop.name or shop.token,
                "source_platform": shop.platform,
                "source_url": offer.source_url or raw.source_url or shop.source_url,
                "original_name": raw.original_name,
                "price": float(offer.price) if offer.price is not None else None,
                "currency": (offer.currency or "CNY"),
                "stock_status": offer.stock_status,
                "stock_count": offer.stock_count,
                "delivery_type": offer.delivery_type,
                "service_period": offer.service_period,
                "warranty": offer.warranty,
                "is_comparable": bool(offer.is_comparable),
                "is_trusted_price": is_trusted,
            })

        product_snapshots.append({
            "id": product.id,
            "slug": product.slug,
            "platform": product.platform,
            "brand": product.platform,
            "display_name": product.display_name,
            "subtitle": product.subtitle or "",
            "product_type": product.product_type or "other",
            "price_currency": "CNY",
            "currency": "CNY",
            "min_price": lowest_price,
            "lowest_price": lowest_price_str,
            "related_lowest_price": related_lowest_price_str,
            "offer_count": offer_count,
            "in_stock_count": in_stock_count,
            "comparable_offer_count": comparable_count,
            "trusted_offer_count": trusted_count,
            "median_price": median_price_str,
            "source_count": source_count,
            "data_quality_score": score,
            "data_quality_label": label,
            "official_reference": official_ref,
            "last_updated_at": latest_obs.isoformat() if latest_obs else None,
            "tags": all_tags,
            "top_5_offers": top_5_offers,
        })

    snapshot_data = {
        "schema_version": "price-radar.v1",
        "snapshot_id": str(snapshot_id),
        "generated_at": (_as_utc(snapshot.created_at) or now_utc).isoformat(),
        "published_at": published_dt.isoformat(),
        "stale": is_stale,
        "ranking_policy_version": "available-non-shared-first.v1",
        "snapshot_url": f"{base_url}/data/v1/snapshots/{snapshot_id}.json",
        "product_count": len(product_snapshots),
        "total": len(product_snapshots),
        "offer_count": total_offers_count,
        "in_stock_count": total_in_stock_count,
        "comparable_offer_count": total_comparable_count,
        "trusted_offer_count": total_trusted_count,
        "metrics_note": "",
        "products": product_snapshots,
    }

    # Write immutable snapshot file. Consumers cache these URLs for a year, so an
    # existing file must never be replaced with different content.
    snapshot_file = snapshots_dir / f"{snapshot_id}.json"
    if snapshot_file.exists():
        logger.info("Snapshot file %s already exists; keeping existing immutable content", snapshot_file)
    else:
        temp_snapshot = snapshots_dir / f".tmp_{snapshot_id}_{os.getpid()}.json"
        with open(temp_snapshot, "w", encoding="utf-8") as f:
            json.dump(snapshot_data, f, ensure_ascii=False, indent=2)
        temp_snapshot.replace(snapshot_file)

    # Write latest.json pointer (only for the current published snapshot)
    latest_pointer = {
        "schema_version": "price-radar.v1",
        "snapshot_id": str(snapshot_id),
        "generated_at": (_as_utc(snapshot.created_at) or now_utc).isoformat(),
        "published_at": published_dt.isoformat(),
        "stale": is_stale,
        "ranking_policy_version": "available-non-shared-first.v1",
        "snapshot_url": f"{base_url}/data/v1/snapshots/{snapshot_id}.json",
        "product_count": len(product_snapshots),
    }

    if is_current_snapshot:
        latest_file = target_dir / "latest.json"
        temp_latest = target_dir / f".tmp_latest_{os.getpid()}.json"
        with open(temp_latest, "w", encoding="utf-8") as f:
            json.dump(latest_pointer, f, ensure_ascii=False, indent=2)
        temp_latest.replace(latest_file)
    else:
        logger.warning(
            "Snapshot %d is not the current published snapshot; latest.json left untouched",
            snapshot_id,
        )

    logger.info("Exported public snapshot %d to %s", snapshot_id, snapshot_file)
    return latest_pointer


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Export public snapshot JSON and latest.json feed")
    parser.add_argument("--snapshot-id", type=int, default=None, help="Snapshot ID to export (defaults to latest)")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", ""))
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--public-base-url", default=None)
    parser.add_argument(
        "--allow-historical",
        action="store_true",
        help="Allow exporting a non-current snapshot for archiving; latest.json is left untouched",
    )
    args = parser.parse_args()

    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")

    db = session_for(args.database_url)
    try:
        pointer = export_public_snapshot(
            db,
            snapshot_id=args.snapshot_id,
            output_dir=args.output_dir,
            public_base_url=args.public_base_url,
            allow_historical=args.allow_historical,
        )
        print(json.dumps(pointer, ensure_ascii=False, indent=2))
    finally:
        db.close()
