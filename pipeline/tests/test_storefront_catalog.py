import copy
import json
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit

import pytest
from price_radar_http import PinnedHTTPSClient, PinnedResponse

from connectors import merchant_json
from connectors.base import SourceFetchError
from storefront_catalog import normalize_storefront_catalog


SOURCE = "https://store.example/api/products"


@pytest.fixture
def catalog():
    now = datetime.now(timezone.utc)
    return {
        "quoteState": "fresh",
        "updatedAt": now.isoformat(),
        "validUntil": (now + timedelta(minutes=5)).isoformat(),
        "suppliers": [{
            "id": "primary", "status": 200, "quoteState": "fresh",
            "updatedAt": now.isoformat(),
            "validUntil": (now + timedelta(minutes=5)).isoformat(),
        }],
        "products": [{
            "id": "supplier:plus & month", "name": "ChatGPT Plus 独享成品号 一个月",
            "category": "ChatGPT Plus", "description": "质保 25 天",
            "supplierId": "primary", "productType": "account",
            "saleEnabled": True, "checkoutSupported": True,
            "price": 10.84, "currency": "USD", "rmbPrice": 72.25, "stock": 18,
        }],
    }


def install_catalog(monkeypatch, catalog):
    calls = []

    class Client:
        normalize_url = staticmethod(PinnedHTTPSClient.normalize_url)

        def __init__(self, **kwargs):
            pass

        def get(self, url, *, accept):
            calls.append(url)
            if url == SOURCE:
                return PinnedResponse(200, {"content-type": "application/json"}, json.dumps(catalog).encode())
            assert url == "https://store.example"
            return PinnedResponse(200, {"content-type": "text/html"}, "<title>AI 优选 — 数字商城</title>".encode())

    monkeypatch.setattr(merchant_json, "PinnedHTTPSClient", Client)
    return calls


def test_storefront_import_uses_displayed_price_and_same_origin_detail(monkeypatch, catalog):
    calls = install_catalog(monkeypatch, catalog)
    record, = merchant_json.load_records(SOURCE)
    assert record["listed_price"] == "72.25"
    assert record["currency"] == "CNY"
    assert record["stock_count"] == 18
    assert record["product_status"] == "in_stock"
    assert record["shop_name"] == "AI 优选"
    assert record["shop_url"] == "https://store.example/"
    assert record["source_platform"] == "merchant_json"
    link = urlsplit(record["product_url"])
    assert link.netloc == "store.example" and link.path == "/product"
    assert parse_qs(link.query) == {"id": [catalog["products"][0]["id"]]}
    assert record["raw_json"]["upstream_price"] == 10.84
    assert record["raw_json"]["upstream_currency"] == "USD"
    assert record["raw_json"]["description"] == "质保 25 天"
    assert calls == [SOURCE, "https://store.example"]


@pytest.mark.parametrize("field,value", [("saleEnabled", False), ("checkoutSupported", False), ("visible", False)])
def test_storefront_does_not_publish_preview_or_disabled_products(catalog, field, value):
    catalog["products"][0][field] = value
    assert normalize_storefront_catalog(catalog, SOURCE)["items"] == []


@pytest.mark.parametrize("stock,kind,expected", [(0, "account", "out_of_stock"), (None, "account", "unknown"), (None, "slot", "in_stock"), (None, "upgrade_account", "in_stock")])
def test_storefront_preserves_stock_semantics(catalog, stock, kind, expected):
    catalog["products"][0].update(stock=stock, productType=kind)
    assert normalize_storefront_catalog(catalog, SOURCE)["items"][0]["stock_status"] == expected


def test_storefront_keeps_original_currency_when_no_displayed_cny_price(catalog):
    catalog["products"][0]["rmbPrice"] = None
    item, = normalize_storefront_catalog(catalog, SOURCE)["items"]
    assert item["price"] == "10.84" and item["currency"] == "USD"


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1, None, True])
def test_storefront_rejects_invalid_prices(catalog, value):
    catalog["products"][0].update(rmbPrice=value, price=value)
    with pytest.raises(ValueError, match="price"):
        normalize_storefront_catalog(catalog, SOURCE)


@pytest.mark.parametrize("target,field,value", [
    ("catalog", "quoteState", "stale"),
    ("catalog", "validUntil", "2020-01-01T00:00:00Z"),
    ("supplier", "quoteState", "stale"),
    ("supplier", "validUntil", "2020-01-01T00:00:00Z"),
    ("supplier", "status", 503),
])
def test_storefront_stale_data_is_a_recoverable_source_failure(monkeypatch, catalog, target, field, value):
    (catalog if target == "catalog" else catalog["suppliers"][0])[field] = value
    install_catalog(monkeypatch, catalog)
    with pytest.raises(SourceFetchError):
        list(merchant_json.load_records(SOURCE))


def test_storefront_partial_supplier_failure_does_not_freshen_stale_quotes(catalog):
    catalog["suppliers"].append({**catalog["suppliers"][0], "id": "second", "quoteState": "stale"})
    catalog["products"].append({**catalog["products"][0], "id": "second:plus", "supplierId": "second"})
    items = normalize_storefront_catalog(catalog, SOURCE)["items"]
    assert [item["id"] for item in items] == [catalog["products"][0]["id"]]


@pytest.mark.parametrize("failure", [TimeoutError(), ConnectionResetError(), 503])
def test_merchant_transport_failure_can_preserve_other_catalog_sources(monkeypatch, failure):
    class Client:
        normalize_url = staticmethod(PinnedHTTPSClient.normalize_url)

        def __init__(self, **kwargs):
            pass

        def get(self, url, *, accept):
            if isinstance(failure, Exception):
                raise failure
            return PinnedResponse(failure, {}, b"")

    monkeypatch.setattr(merchant_json, "PinnedHTTPSClient", Client)
    with pytest.raises(SourceFetchError):
        list(merchant_json.load_records(SOURCE))


def test_storefront_rejects_ambiguous_product_identity_and_unrelated_endpoints(catalog):
    with pytest.raises(ValueError, match="public /api/products"):
        normalize_storefront_catalog(catalog, "https://store.example/arbitrary.json")
    catalog["products"].append(copy.deepcopy(catalog["products"][0]))
    with pytest.raises(ValueError, match="duplicate storefront product"):
        normalize_storefront_catalog(catalog, SOURCE)


def test_storefront_intake_publishes_through_existing_catalog(monkeypatch, catalog, tmp_path):
    from sqlalchemy import select
    from common import Offer, Shop, session_for
    from publish_catalog import SourceSpec, publish_sources
    import export_snapshot

    install_catalog(monkeypatch, catalog)
    monkeypatch.setattr(export_snapshot, "DEFAULT_OUTPUT_DIR", tmp_path / "public-data")
    db = session_for("sqlite://")
    try:
        result = publish_sources(db, [SourceSpec("merchant-json", SOURCE)])
        assert result.imports[0].public_offer_count == 1
        offer = db.scalars(select(Offer)).one()
        shop = db.scalars(select(Shop)).one()
        assert str(offer.price) == "72.25" and offer.currency == "CNY"
        assert offer.service_period == "one_month" and offer.approved
        assert shop.name == "AI 优选"
        snapshot = json.loads((tmp_path / "public-data" / "v1" / "snapshots" / f"{result.snapshot_id}.json").read_text(encoding="utf-8"))
        product = next(p for p in snapshot["products"] if p["slug"] == "chatgpt-plus")
        assert product["offers"][0]["price"] == 72.25
    finally:
        db.close()
