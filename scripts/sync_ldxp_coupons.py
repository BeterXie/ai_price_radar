"""LDXP Coupon Sync Utility

Synchronizes official coupon batches and 10-digit redemption codes from LDXP merchant backend
into Price Radar's `shop_coupons` table. Safe and idempotent to run repeatedly.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal
import logging
import os
import sys
import time

import requests

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for path in [
    os.path.join(BASE_DIR, "apps", "api"),
    os.path.join(BASE_DIR, "pipeline"),
    "/app",
]:
    if os.path.exists(path) and path not in sys.path:
        sys.path.insert(0, path)

from app.database import SessionLocal
from app.models import CouponCampaign, Shop, ShopCoupon

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("sync_ldxp_coupons")

# Merchant credentials must come from the environment; never ship a default.
DEFAULT_MERCHANT_TOKEN = os.getenv("LDXP_MERCHANT_TOKEN", "").strip()
BASE_API = "https://api.wzyp.cn"
MAX_PAGES = 100


def _fetch_paged(url: str, token: str, form: dict[str, str], page_size: int) -> list[dict]:
    """Walk every page so records beyond the first page are not silently dropped."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "token": token,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    results: list[dict] = []
    for page in range(1, MAX_PAGES + 1):
        payload = dict(form, current=str(page), pageSize=str(page_size))
        resp = requests.post(url, headers=headers, data=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 1:
            logger.error(f"Paging stopped at page {page}: {data}")
            break
        page_list = data.get("data", {}).get("list", []) or []
        results.extend(page_list)
        if len(page_list) < page_size:
            break
    return results


def fetch_coupon_batches(token: str) -> list[dict]:
    return _fetch_paged(f"{BASE_API}/merchantApi/SalesCoupon/list", token, {}, page_size=50)


def fetch_coupon_codes(token: str, coupon_id: int, page_size: int = 100) -> list[dict]:
    return _fetch_paged(
        f"{BASE_API}/merchantApi/SalesCoupon/codeList",
        token,
        {"coupon_id": str(coupon_id)},
        page_size=page_size,
    )


def _resolve_ldxp_shop(session) -> tuple[int | None, str, str]:
    """Resolve the LDXP shop binding so coupons are never shop-less."""
    shop = session.query(Shop).filter(Shop.token == "pricememo").first()
    if shop:
        return shop.id, shop.name or "彩头AI", shop.source_url or "https://wzyp.cn/shop/pricememo"
    return None, "彩头AI", "https://wzyp.cn/shop/pricememo"


def sync_coupons(token: str, dry_run: bool = False) -> int:
    session = SessionLocal()
    inserted_count = 0
    try:
        shop_id, shop_name, shop_url = _resolve_ldxp_shop(session)
        if shop_id is None:
            logger.warning("LDXP shop (token=pricememo) not found; coupons will bind by URL only.")

        batches = fetch_coupon_batches(token)
        logger.info(f"Fetched {len(batches)} coupon batches from LDXP.")
        # Campaign seeding and change tracking happen after all batches are read,
        # so per-batch iterations cannot re-create the same campaign.
        existing_campaign_codes = {
            row[0] for row in session.query(CouponCampaign.campaign_code).all()
        }
        reconciled_used = 0

        for batch in batches:
            coupon_id = batch.get("id")
            name = batch.get("name", "专享优惠券")
            discount = Decimal(str(batch.get("money", 5)))
            min_spend = Decimal(str(batch.get("min_money", 0)))
            end_timestamp = batch.get("end_time")
            if end_timestamp:
                expires_at = datetime.fromtimestamp(int(end_timestamp), tz=timezone.utc)
            else:
                expires_at = datetime(2027, 1, 1, tzinfo=timezone.utc)

            logger.info(
                f"Processing batch ID {coupon_id}: {name} (减 {discount} 门槛 {min_spend}), expires {expires_at}"
            )

            codes_data = fetch_coupon_codes(token, coupon_id)
            logger.info(f"Batch {coupon_id} returned {len(codes_data)} codes.")

            for item in codes_data:
                code_str = str(item.get("code", "")).strip()
                if not code_str:
                    continue

                existing = session.query(ShopCoupon).filter(ShopCoupon.code == code_str).first()
                if existing:
                    # Reconcile redemption state from upstream and backfill shop binding.
                    if item.get("status") == 1 and not existing.is_used:
                        existing.is_used = True
                        reconciled_used += 1
                    if existing.shop_id is None and shop_id is not None:
                        existing.shop_id = shop_id
                    continue

                new_coupon = ShopCoupon(
                    coupon_batch_id=coupon_id,
                    name=name,
                    code=code_str,
                    discount_amount=discount,
                    min_spend=min_spend,
                    shop_id=shop_id,
                    shop_name=shop_name,
                    shop_url=shop_url,
                    is_assigned=False,
                    expires_at=expires_at,
                    is_used=bool(item.get("status") == 1),
                )
                if not dry_run:
                    session.add(new_coupon)
                inserted_count += 1

        # Seed default campaigns once, outside the batch loop, and binding them to
        # the resolved shop so redemptions cannot fall back to the site-wide pool.
        last_batch_id = batches[-1].get("id") if batches else 0
        for camp_code, camp_title in [
            ("RADAR888", "雷达站专属回馈口令券 (满15减5)"),
            ("CAITOUAI", "彩头AI小铺直通立减礼包"),
        ]:
            if camp_code in existing_campaign_codes:
                continue
            new_camp = CouponCampaign(
                campaign_code=camp_code,
                title=camp_title,
                coupon_batch_id=last_batch_id,
                shop_id=shop_id,
                shop_name=shop_name,
                shop_url=shop_url,
                max_per_user=1,
                total_quota=100,
                claimed_count=0,
                is_active=True,
                expires_at=datetime(2027, 1, 1, tzinfo=timezone.utc),
            )
            if not dry_run:
                session.add(new_camp)
            existing_campaign_codes.add(camp_code)
            logger.info(f"Created default campaign: {camp_code} ({camp_title})")

        if not dry_run:
            session.commit()
        else:
            session.rollback()
        msg = f"Sync finished. Inserted {inserted_count} new coupon codes."
        if reconciled_used:
            msg += f" Reconciled {reconciled_used} coupons already used upstream."
        logger.info(msg)
        return inserted_count
    except Exception as e:
        session.rollback()
        logger.exception(f"Error syncing LDXP coupons: {e}")
        raise
    finally:
        session.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync LDXP coupon codes to database")
    parser.add_argument("--token", default=DEFAULT_MERCHANT_TOKEN, help="LDXP merchant token")
    parser.add_argument("--dry-run", action="store_true", help="Do not write to database")
    args = parser.parse_args()

    if not args.token.strip():
        print(
            "LDXP merchant token is required: set LDXP_MERCHANT_TOKEN or pass --token",
            file=sys.stderr,
        )
        return 2

    count = sync_coupons(args.token, dry_run=args.dry_run)
    print(f"LDXP coupons sync complete. New codes added: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
