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
from app.models import CouponCampaign, ShopCoupon

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("sync_ldxp_coupons")

DEFAULT_MERCHANT_TOKEN = os.getenv("LDXP_MERCHANT_TOKEN", "182d5854-1b08-4c93-aa06-33189b3971a3")
BASE_API = "https://api.wzyp.cn"


def fetch_coupon_batches(token: str) -> list[dict]:
    url = f"{BASE_API}/merchantApi/SalesCoupon/list"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "token": token,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    resp = requests.post(url, headers=headers, data="current=1&pageSize=50", timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 1:
        logger.error(f"Failed to fetch coupon batches: {data}")
        return []
    return data.get("data", {}).get("list", [])


def fetch_coupon_codes(token: str, coupon_id: int, page_size: int = 100) -> list[dict]:
    url = f"{BASE_API}/merchantApi/SalesCoupon/codeList"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "token": token,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    resp = requests.post(
        url,
        headers=headers,
        data=f"coupon_id={coupon_id}&current=1&pageSize={page_size}",
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 1:
        logger.error(f"Failed to fetch codes for coupon {coupon_id}: {data}")
        return []
    return data.get("data", {}).get("list", [])


def sync_coupons(token: str, dry_run: bool = False) -> int:
    session = SessionLocal()
    inserted_count = 0
    try:
        batches = fetch_coupon_batches(token)
        logger.info(f"Fetched {len(batches)} coupon batches from LDXP.")

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

                # Check if code already recorded in DB
                existing = session.query(ShopCoupon).filter(ShopCoupon.code == code_str).first()
                if existing:
                    continue

                new_coupon = ShopCoupon(
                    coupon_batch_id=coupon_id,
                    name=name,
                    code=code_str,
                    discount_amount=discount,
                    min_spend=min_spend,
                    shop_name="彩头AI",
                    shop_url="https://wzyp.cn/shop/pricememo",
                    is_assigned=False,
                    expires_at=expires_at,
                    is_used=bool(item.get("status") == 1),
                )
                if not dry_run:
                    session.add(new_coupon)
                inserted_count += 1

            # Seed default campaigns if not existing
            for camp_code, camp_title in [
                ("RADAR888", "雷达站专属回馈口令券 (满15减5)"),
                ("CAITOUAI", "彩头AI小铺直通立减礼包"),
            ]:
                campaign = session.query(CouponCampaign).filter(CouponCampaign.campaign_code == camp_code).first()
                if not campaign:
                    new_camp = CouponCampaign(
                        campaign_code=camp_code,
                        title=camp_title,
                        coupon_batch_id=coupon_id,
                        max_per_user=1,
                        total_quota=100,
                        claimed_count=0,
                        is_active=True,
                        expires_at=expires_at,
                    )
                    if not dry_run:
                        session.add(new_camp)
                    logger.info(f"Created default campaign: {camp_code} ({camp_title})")

        if not dry_run:
            session.commit()
        logger.info(f"Sync finished. Inserted {inserted_count} new coupon codes.")
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

    count = sync_coupons(args.token, dry_run=args.dry_run)
    print(f"LDXP coupons sync complete. New codes added: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
