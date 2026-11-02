"""Read and search published JSON quotes without opening a database connection."""
from __future__ import annotations

import json
import os
import re
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from .catalog_vocabulary import BRAND_ALIASES, normalize_search


class SnapshotUnavailable(ValueError):
    pass


@dataclass
class QuoteQuery:
    product: str = ""
    brand: str = ""
    terms: tuple[str, ...] = ()
    delivery: str = ""
    access: str = ""
    period: str = ""
    warranty: str = ""
    stock: str = ""
    currency: str = ""
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    related: bool = False

    @property
    def includes_related(self) -> bool:
        return self.related or self.access == "shared" or self.delivery == "relay_api" or self.stock == "out_of_stock" or self.currency not in ("", "CNY")


def timestamp(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return result.replace(tzinfo=timezone.utc) if result.tzinfo is None else result


def quote_order(row: tuple[dict, dict]) -> tuple:
    offer = row[1]
    price = Decimal(str(offer["price"])) if offer.get("price") is not None else None
    currency = offer.get("currency", "CNY")
    return (
        offer.get("stock_status") != "in_stock", not offer.get("is_comparable"),
        currency != "CNY", currency, price is None, price is not None and price < 1,
        price if price is not None else Decimal("Infinity"),
        -timestamp(offer["observed_at"]).timestamp(), offer["id"],
    )


class SnapshotCatalog:
    def __init__(self, data: dict[str, Any]):
        if data.get("search_schema_version") != 1:
            raise SnapshotUnavailable("报价快照需要更新，请等待下一次价格同步。")
        self.id = str(data["snapshot_id"])
        self.published_at = timestamp(data["published_at"])
        max_age = float(data["stale_offer_hours"])
        if not 1 <= max_age <= 24 * 30:
            raise SnapshotUnavailable("报价快照包含无效有效期，请等待下一次价格同步。")
        self.max_age = timedelta(hours=max_age)
        self.products = {p["slug"]: p for p in data["products"]}
        if len(self.products) != len(data["products"]):
            raise SnapshotUnavailable("报价快照包含重复分类，请等待下一次价格同步。")
        self.aliases: dict[str, set[str]] = {}
        self.brands: dict[str, str] = dict(BRAND_ALIASES)
        self.rows: list[tuple[dict, dict]] = []
        self.by_id: dict[int, tuple[dict, dict]] = {}
        for product in self.products.values():
            for field in ("slug", "brand", "display_name"):
                if not isinstance(product[field], str) or not product[field]:
                    raise SnapshotUnavailable("报价快照包含无效商品分类，请等待下一次价格同步。")
            if not isinstance(product.get("offers"), list) or len(product["offers"]) != product["offer_count"]:
                raise SnapshotUnavailable("报价快照不完整，请等待下一次价格同步。")
            if not isinstance(product["comparable_offer_count"], int) or not 0 <= product["comparable_offer_count"] <= product["offer_count"]:
                raise SnapshotUnavailable("报价快照包含无效分类统计，请等待下一次价格同步。")
            for alias in product.get("search_aliases", [product["slug"], product["display_name"]]):
                normalized = normalize_search(alias)
                if normalized:
                    self.aliases.setdefault(normalized, set()).add(product["slug"])
            for alias in [product["brand"], *product.get("brand_aliases", [])]:
                self.brands[normalize_search(alias)] = product["brand"]
            for offer in product["offers"]:
                # Validate before installing a new snapshot; never partially replace the cache.
                if type(offer["id"]) is not int or offer["id"] in self.by_id:
                    raise SnapshotUnavailable("报价快照包含无效报价标识，请等待下一次价格同步。")
                for field in ("original_name", "shop_name", "shop_token", "stock_status", "delivery_type", "service_period", "warranty", "currency", "account_access"):
                    if not isinstance(offer[field], str):
                        raise SnapshotUnavailable("报价快照包含无效分类，请等待下一次价格同步。")
                for field in ("is_comparable", "is_trusted_price"):
                    if not isinstance(offer[field], bool):
                        raise SnapshotUnavailable("报价快照包含无效价格标记，请等待下一次价格同步。")
                for field in ("item_fingerprint", "source_url"):
                    if offer.get(field) is not None and not isinstance(offer[field], str):
                        raise SnapshotUnavailable("报价快照包含无效商品详情，请等待下一次价格同步。")
                timestamp(offer["observed_at"])
                if offer.get("price") is not None:
                    price = Decimal(str(offer["price"]))
                    if not price.is_finite() or price < 0:
                        raise SnapshotUnavailable("报价快照包含无效价格，请等待下一次价格同步。")
                offer["search_text"] = normalize_search(" ".join([
                    product["display_name"], product["slug"], offer.get("search_text", ""),
                    *product.get("search_keywords", []),
                    offer["original_name"], offer["shop_name"], offer["shop_token"],
                ]))
                self.rows.append((product, offer))
                self.by_id[offer["id"]] = (product, offer)
        if len(self.rows) != data["offer_count"]:
            raise SnapshotUnavailable("报价快照不完整，请等待下一次价格同步。")
        self.by_product = {slug: [] for slug in self.products}
        for row in self.rows:
            self.by_product[row[0]["slug"]].append(row)

    def search(self, query: QuoteQuery, *, now: datetime | None = None) -> list[tuple[dict, dict]]:
        cutoff = (now or datetime.now(timezone.utc)) - self.max_age
        rows = self.by_product.get(query.product, []) if query.product else self.rows
        found = []
        for product, offer in rows:
            if timestamp(offer["observed_at"]) < cutoff:
                continue
            if query.brand and product["brand"] != query.brand:
                continue
            if any(term not in offer["search_text"] for term in query.terms):
                continue
            if not query.includes_related and not (
                offer.get("is_comparable") and offer.get("is_trusted_price")
                and offer.get("stock_status") == "in_stock" and offer.get("currency") == "CNY"
            ):
                continue
            if any(wanted and offer.get(field) != wanted for field, wanted in (
                ("delivery_type", query.delivery), ("account_access", query.access),
                ("service_period", query.period), ("stock_status", query.stock), ("currency", query.currency),
            )):
                continue
            if query.warranty == "covered" and offer.get("warranty", "unknown") in ("none", "unknown"):
                continue
            if query.warranty and query.warranty != "covered" and offer.get("warranty") != query.warranty:
                continue
            price = Decimal(str(offer["price"])) if offer.get("price") is not None else None
            if query.min_price is not None and (price is None or price < query.min_price):
                continue
            if query.max_price is not None and (price is None or price > query.max_price):
                continue
            found.append((product, offer))
        # Keep every quote in the file, and group only after applying the user's filters.
        grouped = {}
        for row in sorted(found, key=quote_order):
            offer = row[1]
            key = (row[0]["slug"], offer.get("item_fingerprint") or str(offer["id"]), offer["currency"])
            grouped.setdefault(key, row)
        return list(grouped.values())


class SnapshotStore:
    def __init__(self):
        self._key: tuple | None = None
        self._catalog: SnapshotCatalog | None = None
        self._lock = threading.Lock()

    def load(self) -> SnapshotCatalog:
        configured = os.getenv("PUBLIC_DATA_DIR", "").strip()
        directory = Path(configured) if configured else next((
            candidate for parent in Path(__file__).resolve().parents
            if (candidate := parent / "apps" / "web" / "public" / "data").is_dir()
        ), Path("data"))
        pointer = directory / "latest.json"
        try:
            with self._lock:
                stat = pointer.stat()
                key = (str(pointer.resolve()), stat.st_mtime_ns, stat.st_size)
                if self._key == key and self._catalog is not None:
                    return self._catalog
                latest = json.loads(pointer.read_text(encoding="utf-8"))
                snapshot_id = str(latest["snapshot_id"])
                if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", snapshot_id):
                    raise SnapshotUnavailable("报价快照标识无效。")
                data = json.loads((directory / "v1" / "snapshots" / f"{snapshot_id}.json").read_text(encoding="utf-8"))
                if str(data["snapshot_id"]) != snapshot_id:
                    raise SnapshotUnavailable("报价快照版本不一致。")
                catalog = SnapshotCatalog(data)
                self._catalog, self._key = catalog, key
                return catalog
        except SnapshotUnavailable:
            raise
        except (OSError, ValueError, TypeError, KeyError, AttributeError, InvalidOperation, OverflowError) as exc:
            raise SnapshotUnavailable("暂时无法读取完整报价快照，请稍后重试。") from exc


snapshot_store = SnapshotStore()
