import copy
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from price_radar_http import PinnedHTTPSClient, PinnedResponse

from connectors import woocommerce_store


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "woocommerce_products.json"


@pytest.fixture
def woocommerce_payload():
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _response(items, *, total=None, total_pages=None, status=200, content_type="application/json"):
    headers = {"content-type": content_type}
    if total is not None:
        headers["x-wp-total"] = str(total)
    if total_pages is not None:
        headers["x-wp-totalpages"] = str(total_pages)
    return PinnedResponse(status, headers, json.dumps(items).encode("utf-8"))


def _install_client(monkeypatch, responder):
    class FakeClient:
        normalize_url = staticmethod(PinnedHTTPSClient.normalize_url)
        init_kwargs = []
        calls = []

        def __init__(self, **kwargs):
            self.init_kwargs.append(kwargs)

        def get(self, url: str, *, accept: str):
            self.calls.append((url, accept))
            return responder(url)

    monkeypatch.setattr(woocommerce_store, "PinnedHTTPSClient", FakeClient)
    return FakeClient


def _catalog_responder(products, variations=None):
    variations = variations or []

    def respond(url: str):
        query = parse_qs(urlsplit(url).query)
        items = variations if query.get("type") == ["variation"] else products
        page = int(query["page"][0])
        page_size = int(query["per_page"][0])
        pages = (len(items) + page_size - 1) // page_size
        start = (page - 1) * page_size
        return _response(
            items[start : start + page_size],
            total=len(items),
            total_pages=pages,
        )

    return respond


def test_woocommerce_paginates_and_converts_minor_units_exactly(
    monkeypatch,
    woocommerce_payload,
):
    monkeypatch.setattr(woocommerce_store, "PAGE_SIZE", 2)
    fake_client = _install_client(
        monkeypatch,
        _catalog_responder(woocommerce_payload["products"]),
    )

    records = list(woocommerce_store.load_records("https://shop.example"))

    assert len(records) == 3
    by_id = {record["raw_json"]["woocommerce_id"]: record for record in records}
    assert by_id[1]["listed_price"] == "900"
    assert by_id[1]["regular_price"] == "1000"
    assert by_id[1]["sale_price"] == "900"
    assert by_id[1]["currency"] == "JPY"
    assert by_id[2]["listed_price"] == "19.99"
    assert by_id[2]["regular_price"] == "24.99"
    assert by_id[2]["sale_price"] == "19.99"
    assert by_id[2]["currency"] == "USD"
    assert by_id[3]["listed_price"] == "12.345"
    assert by_id[3]["regular_price"] == "12.345"
    assert by_id[3]["sale_price"] is None
    assert by_id[3]["currency"] == "KWD"
    assert all(record["source_platform"] == "woocommerce" for record in records)

    assert by_id[1]["product_key"] == "woocommerce:1"
    assert by_id[1]["sku"] == "JPY-1"
    assert by_id[1]["stock_count"] == 0
    assert by_id[1]["product_status"] == "unavailable"
    assert by_id[1]["purchase_status"] == "not_purchasable"
    assert by_id[2]["stock_count"] == 3
    assert by_id[2]["product_status"] == "in_stock"
    assert by_id[2]["category_name"] == "AI Subscriptions"
    assert by_id[3]["product_status"] == "on_backorder"

    assert by_id[1]["raw_json"]["images"][0]["src"] == "https://cdn.example/images/credits.jpg"
    assert "thumbnail" not in by_id[1]["raw_json"]["images"][0]
    assert "link" not in by_id[2]["raw_json"]["categories"][0]
    assert "src" not in by_id[2]["raw_json"]["images"][0]
    assert by_id[2]["raw_json"]["images"][0]["thumbnail"].startswith("https://")

    assert len(fake_client.init_kwargs) == 1
    assert fake_client.init_kwargs[0] == {
        "max_response_bytes": woocommerce_store.MAX_RESPONSE_BYTES,
        "max_task_bytes": woocommerce_store.MAX_TOTAL_BYTES,
        "max_task_seconds": woocommerce_store.MAX_TASK_SECONDS,
        "request_timeout": woocommerce_store.REQUEST_TIMEOUT,
        "user_agent": "AI-Price-Radar-Importer/3.6",
    }
    assert [parse_qs(urlsplit(url).query)["page"][0] for url, _ in fake_client.calls] == ["1", "2"]
    assert all(accept == "application/json" for _, accept in fake_client.calls)


@pytest.mark.parametrize(
    "source",
    [
        "javascript:alert(1)",
        "data:text/plain,hello",
        "file:///C:/secrets.txt",
        "http://shop.example",
        "https://user:password@shop.example",
        "https://shop.example#catalog",
        "https://shop.example:444",
        "https://shop.example/wp-json/wc/store/v1/products",
        "https://shop.example?catalog=1",
        "https://127.0.0.1",
    ],
)
def test_woocommerce_rejects_unsafe_or_noncanonical_sources(source):
    with pytest.raises(ValueError, match="shop root"):
        woocommerce_store._validate_store_url(source)


@pytest.mark.parametrize(
    "unsafe_url",
    [
        "javascript:alert(1)",
        "data:text/html,hello",
        "file:///C:/secrets.txt",
        "http://shop.example/product/item/",
        "https://user:password@shop.example/product/item/",
        "https://shop.example/product/item/#details",
        "https://shop.example:444/product/item/",
    ],
)
def test_woocommerce_rejects_unsafe_product_permalinks(
    monkeypatch,
    woocommerce_payload,
    unsafe_url,
):
    product = copy.deepcopy(woocommerce_payload["products"][0])
    product["permalink"] = unsafe_url
    _install_client(monkeypatch, _catalog_responder([product]))

    with pytest.raises(ValueError, match="product permalink"):
        woocommerce_store.load_records("https://shop.example")


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (PinnedResponse(503, {"content-type": "application/json"}, b"[]"), "HTTP 503"),
        (
            PinnedResponse(200, {"content-type": "text/html"}, b"[]"),
            "JSON content",
        ),
        (
            PinnedResponse(200, {"content-type": "application/json"}, b"not-json"),
            "invalid JSON",
        ),
        (
            PinnedResponse(200, {"content-type": "application/json"}, b"{}"),
            "must be an array",
        ),
        (
            PinnedResponse(200, {"content-type": "application/json"}, b"[]"),
            "x-wp-total",
        ),
    ],
)
def test_woocommerce_rejects_exceptional_responses(monkeypatch, response, message):
    _install_client(monkeypatch, lambda _url: response)

    with pytest.raises(ValueError, match=message):
        woocommerce_store.load_records("https://shop.example")


def test_woocommerce_fails_before_returning_incomplete_pagination(
    monkeypatch,
    woocommerce_payload,
):
    monkeypatch.setattr(woocommerce_store, "PAGE_SIZE", 2)
    products = woocommerce_payload["products"]

    def respond(url: str):
        page = int(parse_qs(urlsplit(url).query)["page"][0])
        if page == 1:
            return _response(products[:2], total=3, total_pages=2)
        return _response([], total=3, total_pages=2)

    _install_client(monkeypatch, respond)

    with pytest.raises(ValueError, match="incomplete pagination"):
        woocommerce_store.load_records("https://shop.example")


def test_woocommerce_rejects_product_and_page_limits(monkeypatch, woocommerce_payload):
    products = woocommerce_payload["products"][:2]
    monkeypatch.setattr(woocommerce_store, "MAX_PRODUCTS", 1)
    _install_client(monkeypatch, _catalog_responder(products))
    with pytest.raises(ValueError, match="product limit"):
        woocommerce_store.load_records("https://shop.example")

    monkeypatch.setattr(woocommerce_store, "MAX_PRODUCTS", 2_000)
    monkeypatch.setattr(woocommerce_store, "PAGE_SIZE", 1)
    monkeypatch.setattr(woocommerce_store, "MAX_PAGES", 1)
    _install_client(monkeypatch, _catalog_responder(products))
    with pytest.raises(ValueError, match="page limit"):
        woocommerce_store.load_records("https://shop.example")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("currency_minor_unit", True),
        ("currency_minor_unit", 13),
        ("price", "19.99"),
        ("regular_price", "-100"),
    ],
)
def test_woocommerce_rejects_invalid_minor_unit_prices(
    monkeypatch,
    woocommerce_payload,
    field,
    value,
):
    product = copy.deepcopy(woocommerce_payload["products"][1])
    product["prices"][field] = value
    _install_client(monkeypatch, _catalog_responder([product]))

    with pytest.raises(ValueError, match="minor_unit|minor units"):
        woocommerce_store.load_records("https://shop.example")


def test_woocommerce_expands_only_complete_public_variations(
    monkeypatch,
    woocommerce_payload,
):
    parent = woocommerce_payload["variable_parent"]
    variations = woocommerce_payload["variations"]
    fake_client = _install_client(
        monkeypatch,
        _catalog_responder([parent], variations),
    )

    records = list(woocommerce_store.load_records("https://shop.example"))

    assert len(records) == 2
    by_id = {record["raw_json"]["woocommerce_id"]: record for record in records}
    monthly = by_id[101]
    assert monthly["product_key"] == "woocommerce:10:variation:101"
    assert monthly["variant_key"] == "101"
    assert monthly["sku"] == "TEAM-MONTHLY-5"
    assert monthly["product_name"] == "ChatGPT team plan · Billing: Monthly / Seats: 5"
    assert monthly["listed_price"] == "18.00"
    assert monthly["regular_price"] == "20.00"
    assert monthly["sale_price"] == "18.00"
    assert monthly["stock_count"] == 4
    assert monthly["category_name"] == "Team Plans"
    assert monthly["raw_json"]["variation_attributes"] == [
        {"name": "Billing", "value": "Monthly"},
        {"name": "Seats", "value": "5"},
    ]
    assert by_id[102]["listed_price"] == "180.00"
    assert by_id[102]["product_status"] == "out_of_stock"

    assert len(fake_client.calls) == 2
    for url, _accept in fake_client.calls:
        assert urlsplit(url).path == "/wp-json/wc/store/v1/products"
    assert parse_qs(urlsplit(fake_client.calls[1][0]).query)["type"] == ["variation"]


@pytest.mark.parametrize(
    "incomplete_case",
    ["missing_variation", "missing_attribute", "missing_price", "unsafe_permalink"],
)
def test_woocommerce_keeps_parent_when_variation_data_is_incomplete(
    monkeypatch,
    woocommerce_payload,
    incomplete_case,
):
    parent = copy.deepcopy(woocommerce_payload["variable_parent"])
    variations = copy.deepcopy(woocommerce_payload["variations"])
    if incomplete_case == "missing_variation":
        variations.pop()
    elif incomplete_case == "missing_attribute":
        parent["variations"][1]["attributes"][0]["value"] = ""
    elif incomplete_case == "missing_price":
        variations[1]["prices"]["price"] = ""
    else:
        variations[1]["permalink"] = "http://shop.example/product/unsafe/"
    fake_client = _install_client(
        monkeypatch,
        _catalog_responder([parent], variations),
    )

    records = list(woocommerce_store.load_records("https://shop.example"))

    assert len(records) == 1
    record = records[0]
    assert record["product_key"] == "woocommerce:10"
    assert record["variant_key"] == ""
    assert record["product_name"] == "ChatGPT team plan"
    assert record["listed_price"] == "15.00"
    assert all(urlsplit(url).path == "/wp-json/wc/store/v1/products" for url, _ in fake_client.calls)


def test_woocommerce_not_purchasable_never_counts_as_in_stock(
    monkeypatch,
    woocommerce_payload,
):
    product = copy.deepcopy(woocommerce_payload["products"][1])
    product["is_in_stock"] = True
    product["is_purchasable"] = False
    _install_client(monkeypatch, _catalog_responder([product]))

    record = next(iter(woocommerce_store.load_records("https://shop.example")))

    assert record["stock_count"] == 0
    assert record["product_status"] == "unavailable"
    assert record["purchase_status"] == "not_purchasable"

    from sqlalchemy import select

    from common import Offer, ensure_products, session_for, upsert_offer

    db = session_for("sqlite://")
    try:
        products = ensure_products(db)
        upsert_offer(db, record, products)
        db.flush()
        offer = db.scalars(select(Offer)).one()
        assert offer.stock_status != "in_stock"
    finally:
        db.close()


def test_woocommerce_records_persist_canonical_platform(monkeypatch, woocommerce_payload):
    _install_client(monkeypatch, _catalog_responder(woocommerce_payload["products"]))

    from sqlalchemy import select

    from common import Shop, ensure_products, session_for, upsert_offer

    db = session_for("sqlite://")
    try:
        products = ensure_products(db)
        for record in woocommerce_store.load_records("https://shop.example"):
            upsert_offer(db, record, products)
        db.flush()
        shops = list(db.scalars(select(Shop)))
        assert len(shops) == 1
        assert shops[0].platform == "woocommerce"
    finally:
        db.close()
