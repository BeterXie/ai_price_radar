from __future__ import annotations

from argparse import Namespace
from decimal import Decimal

import pytest

from common import CatalogSnapshot, Offer, RawProduct, Shop, session_for
from connectors import CONNECTORS, kmdian
from connectors.base import SourceFetchError
from publish_catalog import SourceImportError, SourceSpec, _build_sources, publish_sources


def record(shop="S1", goods="KM1", price="27.50", platform="kmdian"):
    return {
        "token": f"{platform}-{shop}", "shop_name": "API 店铺",
        "shop_url": f"https://www.kmdian.com/shop/{shop}", "source_platform": platform,
        "product_key": f"{platform}:{goods}", "product_name": "ChatGPT Plus 直充一个月",
        "product_url": f"https://www.kmdian.com/item/{goods}",
        "listed_price": price, "currency": "CNY", "stock_count": 5, "product_status": "in_stock",
        "raw_json": {"sales_count": 7},
    }


@pytest.fixture
def db(monkeypatch, tmp_path):
    monkeypatch.setenv("PUBLIC_DATA_DIR", str(tmp_path / "feed"))
    session = session_for("sqlite://")
    try:
        yield session
    finally:
        session.close()
        session.get_bind().dispose()


def test_configured_key_adds_the_full_platform_to_authoritative_publication(monkeypatch):
    args = Namespace(ldxp_db=None, dujiao_db=None, merchant_sources=None)
    monkeypatch.delenv(kmdian.API_KEY_ENV, raising=False)
    assert _build_sources(args) == []
    monkeypatch.setenv(kmdian.API_KEY_ENV, "test-app.test-secret")
    assert _build_sources(args) == [SourceSpec("kmdian", kmdian.API_URL)]


@pytest.mark.parametrize("remaining", [[record()], []])
@pytest.mark.parametrize("carry_forward", [False, True])
def test_sync_is_idempotent_and_removes_missing_shops_without_affecting_other_platforms(db, monkeypatch, remaining, carry_forward):
    monkeypatch.setitem(CONNECTORS, "kmdian", lambda _: iter([record(), record("S2", "KM2")]))
    monkeypatch.setitem(CONNECTORS, "merchant-json", lambda _: iter([record(platform="merchant_json")]))
    all_sources = [SourceSpec("kmdian", kmdian.API_URL), SourceSpec("merchant-json", "other")]
    first = publish_sources(db, all_sources)
    assert first.offer_count == 3
    assert db.query(RawProduct).filter(RawProduct.source_product_key == "kmdian:KM1").one().raw_json["sales_count"] == 7
    monkeypatch.setitem(CONNECTORS, "kmdian", lambda _: iter(remaining))
    result = publish_sources(db, all_sources[:1] if carry_forward else all_sources, carry_forward_current=carry_forward)
    assert result.offer_count == len(remaining) + 1
    assert db.query(Shop).count() == 3
    assert db.query(Offer).count() == 3
    active = db.query(Offer).filter(Offer.snapshot_id == result.snapshot_id).all()
    assert {db.get(Shop, offer.shop_id).platform for offer in active} == ({"kmdian", "merchant_json"} if remaining else {"merchant_json"})
    assert result.imports[0].created == 0
    if carry_forward:
        assert result.imports[0].pruned == 2 - len(remaining)


@pytest.mark.parametrize("carry_forward", [False, True])
def test_partial_fetch_failure_preserves_all_platform_shops_and_observation_times(db, monkeypatch, carry_forward):
    monkeypatch.setitem(CONNECTORS, "kmdian", lambda _: iter([record(), record("S2", "KM2")]))
    monkeypatch.setitem(CONNECTORS, "merchant-json", lambda _: iter([record(platform="merchant_json")]))
    sources = [SourceSpec("kmdian", kmdian.API_URL), SourceSpec("merchant-json", "other")]
    publish_sources(db, sources)
    before = {offer.id: (offer.price, offer.observed_at) for offer in db.query(Offer).join(Shop).filter(Shop.platform == "kmdian")}

    def fail(_):
        yield record(price="99.00")
        raise SourceFetchError("HTTP 503")

    monkeypatch.setitem(CONNECTORS, "kmdian", fail)
    result = publish_sources(db, sources, carry_forward_current=carry_forward)
    db.expire_all()
    assert result.offer_count == 3
    assert result.imports[0].status == "fetch_failed"
    after = {offer.id: (offer.price, offer.observed_at) for offer in db.query(Offer).join(Shop).filter(Shop.platform == "kmdian")}
    assert after == before
    assert all(offer.snapshot_id == result.snapshot_id for offer in db.query(Offer))


def test_incomplete_pagination_does_not_publish_partial_platform_data(db, monkeypatch):
    monkeypatch.setitem(CONNECTORS, "kmdian", lambda _: iter([record()]))
    sources = [SourceSpec("kmdian", kmdian.API_URL)]
    previous = publish_sources(db, sources)

    def incomplete(_):
        yield record(price="99.00")
        raise ValueError("kmdian API returned an incomplete page")

    monkeypatch.setitem(CONNECTORS, "kmdian", incomplete)
    with pytest.raises(SourceImportError, match="incomplete page"):
        publish_sources(db, sources)
    db.expire_all()
    assert db.query(CatalogSnapshot).count() == 1
    assert db.query(Offer).one().snapshot_id == previous.snapshot_id
    assert db.query(Offer).one().price == Decimal("27.50")


@pytest.mark.parametrize("key_present", [True, False])
def test_full_publication_refuses_to_drop_an_omitted_kmdian_source(db, monkeypatch, key_present):
    monkeypatch.setenv(kmdian.API_KEY_ENV, "test-app.test-secret")
    monkeypatch.setitem(CONNECTORS, "kmdian", lambda _: iter([record()]))
    publish_sources(db, [SourceSpec("kmdian", kmdian.API_URL)])
    if not key_present:
        monkeypatch.delenv(kmdian.API_KEY_ENV)
    monkeypatch.setitem(CONNECTORS, "merchant-json", lambda _: iter([record(platform="merchant_json")]))
    with pytest.raises(SourceImportError, match="KMDian source is not included"):
        publish_sources(db, [SourceSpec("merchant-json", "other")])


def test_legacy_ldxp_upsert_cannot_take_over_a_kmdian_shop(db, monkeypatch):
    from common import ensure_products, upsert_offer
    monkeypatch.setitem(CONNECTORS, "kmdian", lambda _: iter([record()]))
    publish_sources(db, [SourceSpec("kmdian", kmdian.API_URL)])
    legacy_record = record(platform="ldxp")
    legacy_record["token"] = "kmdian-S1"
    legacy_record.pop("source_platform")  # Old LDXP/CSV callers omit this field.
    with pytest.raises(ValueError, match="belongs to platform"):
        upsert_offer(db, legacy_record, ensure_products(db))
    assert db.query(Shop).one().platform == "kmdian"


def test_csv_platform_case_does_not_change_the_persisted_platform(db, monkeypatch):
    from common import ensure_products, upsert_offer
    monkeypatch.setitem(CONNECTORS, "kmdian", lambda _: iter([record()]))
    publish_sources(db, [SourceSpec("kmdian", kmdian.API_URL)])
    csv_row = {**record(), "source_platform": "KMDian"}
    upsert_offer(db, csv_row, ensure_products(db))
    db.commit()
    assert db.query(Shop).one().platform == "kmdian"
    # A regular connector refresh must still recognize the same store.
    assert publish_sources(db, [SourceSpec("kmdian", kmdian.API_URL)]).offer_count == 1
