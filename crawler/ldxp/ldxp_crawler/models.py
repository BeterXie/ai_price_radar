from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(slots=True)
class ProductMatch:
    product_key: str
    product_name: str
    matched_keywords: list[str]
    listed_price: Optional[float] = None
    real_price: Optional[float] = None
    stock_count: Optional[int] = None
    product_status: str = "库存未知"
    category_name: str = ""
    product_url: str = ""
    auto_delivery: str = "未知"
    goods_type: str = ""
    content_hash: str = ""
    redacted_field_count: int = 0


@dataclass(slots=True)
class ShopScanResult:
    token: str
    status: str
    shop_name: str = ""
    shop_url: str = ""
    api_host: str = ""
    scanned_item_count: int = 0
    request_count: int = 0
    matches: list[ProductMatch] = field(default_factory=list)
    error: str = ""
    challenge_seen: bool = False
    http_status: Optional[int] = None
    engine: str = "browser"

    @property
    def is_successful_scan(self) -> bool:
        return self.status in {"success", "partial_success", "no_match", "empty_shop", "closed"}
