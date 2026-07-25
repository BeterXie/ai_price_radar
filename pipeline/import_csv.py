from __future__ import annotations

import argparse
import os
import csv
from pathlib import Path

from common import ImportLockUnavailable, ensure_products, import_lock, session_for, upsert_offer

HEADER_MAP = {
    "店铺Token": "token", "店铺名称": "shop_name", "店铺链接": "shop_url",
    "商品名称": "product_name", "标价": "listed_price", "库存": "stock_count",
    "状态": "product_status", "分类": "category_name", "商品链接": "product_url",
    "自动发货": "auto_delivery", "采集时间": "collected_at", "API域名": "api_host",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Import crawler product CSV")
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", ""))
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")
    db = session_for(args.database_url)
    total = failed = 0
    try:
        with import_lock(db):
            products = ensure_products(db)
            with args.csv.open("r", encoding="utf-8-sig", newline="") as handle:
                for row in csv.DictReader(handle):
                    total += 1
                    record = {HEADER_MAP.get(key, key): value for key, value in row.items()}
                    record["product_key"] = record.get("product_url") or record.get("product_name")
                    try:
                        upsert_offer(db, record, products)
                    except Exception as exc:
                        failed += 1
                        print(f"row {total}: {exc}")
            db.commit()
    except ImportLockUnavailable as exc:
        db.rollback()
        print(f"error: {exc}")
        return 3
    finally:
        db.close()
    print(f"imported={total - failed} failed={failed}")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
