"""Preview or apply the shared account classifier to historical offers.

Defaults to a read-only preview. Use --apply after reviewing the transitions.
The admin repair path preserves manual classifications and moderation state.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.database import SessionLocal
from app.models import Offer, Product
from app.services.offer_classification import classify_offer


def preview(db, *, published_only: bool = False) -> dict:
    products = dict(db.execute(select(Product.id, Product.slug)).all())
    transitions: Counter = Counter()
    delivery_transitions: Counter = Counter()
    scanned = skipped = 0
    if published_only:
        from app.services.catalog import _base_public_offer_query
        query = _base_public_offer_query(db).join(Product, Offer.product_id == Product.id).where(Product.is_visible.is_(True))
    else:
        query = select(Offer).options(joinedload(Offer.raw_product), joinedload(Offer.shop))
    offers = db.scalars(
        query
        .order_by(Offer.id)
        .execution_options(yield_per=500)
    )
    for offer in offers:
        scanned += 1
        if "manual_override" in (offer.tags or []) or (offer.classification_confidence or 0) >= 100:
            skipped += 1
            continue
        result = classify_offer(offer)
        target = result.slug
        previous = products.get(offer.product_id)
        if previous != target:
            transitions[(previous or "unclassified", target or "unclassified")] += 1
        if offer.delivery_type != result.delivery_type:
            delivery_transitions[(offer.delivery_type or "unknown", result.delivery_type)] += 1
    return {
        "scanned": scanned,
        "manual_skipped": skipped,
        "changed": sum(transitions.values()),
        "delivery_changed": sum(delivery_transitions.values()),
        "delivery_transitions": [
            {"from": before, "to": after, "count": count}
            for (before, after), count in sorted(delivery_transitions.items())
        ],
        "transitions": [
            {"from": before, "to": after, "count": count}
            for (before, after), count in sorted(transitions.items())
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="Apply the shared admin reclassification")
    mode.add_argument("--dry-run", action="store_true", help="Read-only preview (default)")
    parser.add_argument("--published-only", action="store_true", help="Limit repair to the current public catalog; preserve hidden and historical offers")
    args = parser.parse_args()
    with SessionLocal() as db:
        print(json.dumps({"dry_run": not args.apply, **preview(db, published_only=args.published_only)}, ensure_ascii=False, indent=2))
        if args.apply:
            from app.routers.admin import reclassify

            print(json.dumps(reclassify(db, published_only=args.published_only), ensure_ascii=False))


if __name__ == "__main__":
    main()
