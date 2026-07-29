import json
from pathlib import Path

from connectors import get_connector
from connectors.merchant_json import _validate_remote_url


def test_merchant_json_connector_normalizes_feed(tmp_path: Path):
    source = tmp_path / "feed.json"
    source.write_text(json.dumps({
        "shop": {"name": "Example merchant", "url": "https://merchant.example"},
        "updated_at": "2026-07-29T00:00:00+00:00",
        "items": [{
            "id": "plus-1",
            "name": "ChatGPT Plus 月卡",
            "url": "https://merchant.example/products/plus-1",
            "price": "99.00",
            "stock_count": 5,
            "stock_status": "in_stock",
            "auto_delivery": True,
        }],
    }, ensure_ascii=False), encoding="utf-8")

    records = list(get_connector("merchant-json")(source))
    assert len(records) == 1
    record = records[0]
    assert record["source_platform"] == "merchant_json"
    assert record["product_name"] == "ChatGPT Plus 月卡"
    assert record["listed_price"] == "99.00"
    assert record["token"].startswith("feed-")


def test_connector_registry_rejects_unknown_connector():
    try:
        get_connector("missing")
    except ValueError as exc:
        assert "unknown connector" in str(exc)
    else:
        raise AssertionError("unknown connector should fail")


def test_merchant_connector_rejects_non_public_hosts():
    for value in ("http://example.com/feed.json", "https://localhost/feed.json", "https://127.0.0.1/feed.json"):
        try:
            _validate_remote_url(value)
        except ValueError:
            pass
        else:
            raise AssertionError(f"unsafe URL should fail: {value}")
