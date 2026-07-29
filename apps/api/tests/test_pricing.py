from decimal import Decimal

from app.services.pricing import is_trusted_price, low_price_warning, price_median


def test_price_median_ignores_missing_and_non_positive_values():
    assert price_median([None, Decimal("0"), Decimal("10"), Decimal("20")]) == Decimal("15")


def test_sub_yuan_price_is_not_trusted():
    price = Decimal("0.01")
    assert is_trusted_price(price, Decimal("20")) is False
    assert low_price_warning(price, Decimal("20")) == "价格低于 ¥1，请核对是否为体验、余额或受限商品。"


def test_large_downward_outlier_is_not_trusted():
    assert is_trusted_price(Decimal("5"), Decimal("20")) is False
    assert "低约 75%" in (low_price_warning(Decimal("5"), Decimal("20")) or "")


def test_normal_comparable_price_is_trusted():
    assert is_trusted_price(Decimal("15"), Decimal("20")) is True
