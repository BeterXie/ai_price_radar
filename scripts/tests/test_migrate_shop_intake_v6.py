from scripts.migrate_shop_intake_v6 import historical_intake_status, normalize_historical_source


def test_historical_source_key_normalization():
    key, url = normalize_historical_source(
        "ldxp",
        "http://PAY.LDXP.CN/shop/AbC123/?from=old-report",
        1,
    )
    assert key == "abc123"
    assert url == "https://pay.ldxp.cn/shop/AbC123"

    feed_key, feed_url = normalize_historical_source(
        "merchant_feed",
        "https://Merchant.Example/feed.json?format=full",
        2,
    )
    assert feed_key == "https://merchant.example/feed.json?format=full"
    assert feed_url == feed_key


def test_historical_status_reopens_old_resolved_reports():
    assert historical_intake_status("resolved", known_source=False) == "pending_review"
    assert historical_intake_status("rejected", known_source=False) == "rejected"
    assert historical_intake_status("resolved", known_source=True) == "onboarded"
