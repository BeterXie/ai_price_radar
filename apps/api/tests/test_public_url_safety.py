from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.models import CouponCampaign, ShopCoupon
from app.routers.admin import _admin_campaign_to_read
from app.routers.user import _coupon_to_read
from app.schemas import AdminCampaignCreate, AdminCouponImportRequest
from app.services.source_platform import normalize_public_https_url, public_https_url_or_empty


def _url(scheme: str, target: str) -> str:
    return f"{scheme}:{target}"


def test_public_https_url_normalization_fails_closed() -> None:
    safe = _url("https", "//example.com/store?campaign=1#fragment")
    assert normalize_public_https_url(safe) == _url("https", "//example.com/store?campaign=1")

    unsafe_values = (
        _url("http", "//example.com/store"),
        _url("javascript", "alert(1)"),
        _url("https", "//127.0.0.1/private"),
        _url("https", "//localhost/private"),
        _url("https", "//user:secret@example.com/private"),
    )
    assert all(public_https_url_or_empty(value) == "" for value in unsafe_values)


@pytest.mark.parametrize(
    "unsafe_url",
    [
        _url("http", "//example.com/store"),
        _url("javascript", "alert(1)"),
        _url("https", "//10.0.0.1/private"),
    ],
)
def test_coupon_admin_payloads_reject_non_public_https_urls(unsafe_url: str) -> None:
    with pytest.raises(ValidationError):
        AdminCouponImportRequest(shop_url=unsafe_url, codes_text="CODE-1")
    with pytest.raises(ValidationError):
        AdminCampaignCreate(campaign_code="SAFE1", title="Safe campaign", shop_url=unsafe_url)


def test_legacy_coupon_and_campaign_urls_are_hidden() -> None:
    now = datetime.now(timezone.utc)
    unsafe_url = _url("javascript", "alert(1)")
    coupon = ShopCoupon(
        id=1,
        coupon_batch_id=0,
        name="Legacy coupon",
        code="LEGACY-1",
        discount_amount=Decimal("5.00"),
        min_spend=Decimal("10.00"),
        shop_name="Legacy shop",
        shop_url=unsafe_url,
        is_assigned=False,
        expires_at=now + timedelta(days=1),
        is_used=False,
        created_at=now,
    )
    campaign = CouponCampaign(
        id=1,
        campaign_code="LEGACY-CAMPAIGN",
        title="Legacy campaign",
        coupon_batch_id=0,
        shop_url=unsafe_url,
        max_per_user=1,
        total_quota=1,
        claimed_count=0,
        is_active=True,
        expires_at=now + timedelta(days=1),
        created_at=now,
    )

    assert _coupon_to_read(coupon).shop_url == ""
    assert _admin_campaign_to_read(campaign).shop_url is None
