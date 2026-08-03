from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from statistics import median

MIN_TRUSTED_PRICE = Decimal("1")
LOW_PRICE_RATIO = Decimal("0.4")


def price_median(values: Iterable[Decimal | None]) -> Decimal | None:
    """Return a decimal median for positive prices only."""
    normalized = [value for value in values if value is not None and value > 0]
    if not normalized:
        return None
    return Decimal(str(median(normalized)))


def low_price_warning(price: Decimal | None, median_price: Decimal | None, currency: str = "CNY") -> str | None:
    """Explain why a price should be reviewed instead of promoted as trustworthy."""
    if price is None or price <= 0:
        return None
    if price < MIN_TRUSTED_PRICE:
        unit = "¥1" if currency == "CNY" else f"{currency} 1"
        return f"价格低于 {unit}，请核对是否为体验、余额或受限商品。"
    if median_price and median_price > 0 and price < median_price * LOW_PRICE_RATIO:
        percentage = max(1, round((Decimal("1") - price / median_price) * 100))
        return f"该报价比同交付形态中位价低约 {percentage}%，请重点核对。"
    return None


def is_trusted_price(price: Decimal | None, median_price: Decimal | None) -> bool:
    """A trusted price is positive and does not trigger the anomaly rules."""
    return price is not None and price > 0 and low_price_warning(price, median_price) is None
