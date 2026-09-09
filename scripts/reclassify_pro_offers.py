"""
Reclassify existing offers under generic chatgpt-pro (id=3) to chatgpt-pro-5x (id=33) or chatgpt-pro-20x (id=34).
Also sets product chatgpt-pro is_visible = False.
Can run both locally and inside docker container on production.
"""
from __future__ import annotations

import os
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for path in [
    os.path.join(BASE_DIR, "apps", "api"),
    os.path.join(BASE_DIR, "pipeline"),
    "/app",
]:
    if os.path.exists(path) and path not in sys.path:
        sys.path.insert(0, path)

from app.database import SessionLocal
from app.models import Product, Offer, RawProduct
from app.services.classifier import _pro_multiplier


def reclassify_pro_offers(dry_run: bool = False) -> None:
    session = SessionLocal()
    try:
        pro = session.query(Product).filter(Product.slug == "chatgpt-pro").first()
        pro_5x = session.query(Product).filter(Product.slug == "chatgpt-pro-5x").first()
        pro_20x = session.query(Product).filter(Product.slug == "chatgpt-pro-20x").first()

        if not pro:
            print("[INFO] Product 'chatgpt-pro' not found in database. Nothing to reclassify.")
            return
        if not pro_5x or not pro_20x:
            print("[ERROR] Required products 'chatgpt-pro-5x' or 'chatgpt-pro-20x' not found in database!")
            return

        print(f"[INFO] Found products:")
        print(f"  - chatgpt-pro: id={pro.id}, is_visible={pro.is_visible}")
        print(f"  - chatgpt-pro-5x: id={pro_5x.id}, is_visible={pro_5x.is_visible}")
        print(f"  - chatgpt-pro-20x: id={pro_20x.id}, is_visible={pro_20x.is_visible}")

        offers = session.query(Offer).filter(Offer.product_id == pro.id).all()
        print(f"[INFO] Total offers under chatgpt-pro (id={pro.id}): {len(offers)}")

        count_5x = 0
        count_20x = 0

        for offer in offers:
            raw = offer.raw_product
            title = raw.original_name if raw else ""
            category = raw.original_category if raw else ""
            full_text = f"{title} {category}"

            # Check multiplier using updated logic
            mult = _pro_multiplier(full_text)
            if mult == 5:
                target = pro_5x
                count_5x += 1
            else:
                # Default generic Pro / 20x / 200刀 to chatgpt-pro-20x
                target = pro_20x
                count_20x += 1

            print(f"  Offer #{offer.id} ({float(offer.price or 0)} CNY) '{title}': -> {target.slug} (id={target.id})")
            if not dry_run:
                offer.product_id = target.id

        if not dry_run:
            pro.is_visible = False
            session.commit()
            print(f"[SUCCESS] Reclassified {len(offers)} offers:")
            print(f"  - To chatgpt-pro-5x: {count_5x}")
            print(f"  - To chatgpt-pro-20x: {count_20x}")
            print(f"  - Set chatgpt-pro is_visible: False")

            # Verify count
            remaining = session.query(Offer).filter(Offer.product_id == pro.id).count()
            print(f"[VERIFY] Remaining offers under chatgpt-pro (id={pro.id}): {remaining}")
            assert remaining == 0, f"Expected 0 remaining offers, got {remaining}"
        else:
            print(f"[DRY RUN] Would reclassify {count_5x} to 5x, {count_20x} to 20x.")
    finally:
        session.close()


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    reclassify_pro_offers(dry_run=dry_run)
