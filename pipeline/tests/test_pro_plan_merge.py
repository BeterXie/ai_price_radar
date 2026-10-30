"""Pro plan merge contracts using the pipeline's independent SQLAlchemy Base."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import inspect, select

from common import (
    CatalogSnapshot, Offer, OfferHistory, Product, RawProduct, Shop,
    classify, ensure_products, session_for, upsert_offer,
)


PLAN_PAIRS = (
    ("chatgpt-pro-5x", "chatgpt-pro-100"),
    ("chatgpt-pro-20x", "chatgpt-pro-200"),
)


@pytest.fixture
def merge_db():
    db = session_for("sqlite://")
    engine = db.get_bind()
    # Importing the shared merge helper must not require API-only tables.
    assert "user_product_subscriptions" not in inspect(engine).get_table_names()
    assert "community_skills" not in inspect(engine).get_table_names()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def _rows(db, model):
    return {
        row["id"]: deepcopy(dict(row))
        for row in db.execute(select(model.__table__).order_by(model.id)).mappings()
    }


def _seed_legacy_catalog(db, *, canonical_visible=True):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    old = now - timedelta(days=10)
    shop = Shop(token="pipeline-pro-merge", name="Merchant", source_url="https://example.com/shop")
    snapshots = [
        CatalogSnapshot(source="old", published_at=old, created_at=old, offer_count=2),
        CatalogSnapshot(source="current", published_at=now, created_at=now, offer_count=4),
    ]
    products = {}
    for legacy, canonical in PLAN_PAIRS:
        products[legacy] = Product(slug=legacy, platform="OpenAI", display_name=legacy)
        if canonical_visible is not None:
            products[canonical] = Product(
                slug=canonical, platform="OpenAI", display_name=canonical, is_visible=canonical_visible,
            )
    products["control-product"] = Product(slug="control-product", platform="Other", display_name="Unrelated")
    db.add_all([shop, *snapshots, *products.values()])
    db.flush()

    def add_offer(key, slug, *, snapshot, manual=False, observed_at=now, title=None):
        raw = RawProduct(
            shop_id=shop.id, source_product_key=key,
            original_name=title or f"ChatGPT Pro {slug.rsplit('-', 1)[-1]} 月卡",
            original_category="商家原始 5x / 20x 分类", source_url=f"https://example.com/{key}",
            raw_json={"description": "<p>原始 5x/20x 描述 &amp; 质保约定</p>", "sku": {"key": key}},
            first_seen_at=old, last_seen_at=observed_at,
        )
        db.add(raw)
        db.flush()
        offer = Offer(
            raw_product_id=raw.id, product_id=products[slug].id if slug is not None else None,
            shop_id=shop.id, snapshot_id=snapshot.id if snapshot else None,
            price=Decimal("123.45"), currency="CNY", stock_count=9, stock_status="in_stock",
            auto_delivery=True, tags=["manual_override", "手工标签"] if manual else ["月付"],
            risk_flags=["保留原提示"], classification_confidence=100 if manual else 81,
            delivery_type="finished_account", is_comparable=True, service_period="one_month",
            warranty="first_login", use_scenarios=["coding"], item_fingerprint=f"fingerprint-{key}",
            source_url=raw.source_url, observed_at=observed_at,
            active=not manual, approved=not manual, hidden_reason="人工隐藏" if manual else "",
            click_count=17, created_at=old, updated_at=old + timedelta(hours=1),
        )
        db.add(offer)
        db.flush()
        db.add(OfferHistory(
            offer_id=offer.id, price=Decimal("135.79"), currency="CNY",
            stock_count=2, stock_status="out_of_stock", observed_at=old,
        ))

    for legacy, canonical in PLAN_PAIRS:
        add_offer(f"{legacy}-current", legacy, snapshot=snapshots[1])
        add_offer(
            f"{legacy}-manual", legacy, snapshot=snapshots[1], manual=True,
            title="人工指定分类，无套餐关键字",
        )
        add_offer(f"{legacy}-historical", legacy, snapshot=snapshots[0], observed_at=old)
        add_offer(f"{legacy}-no-snapshot", legacy, snapshot=None, observed_at=old)
        if canonical in products:
            add_offer(f"{canonical}-current", canonical, snapshot=snapshots[1])
    add_offer("control", "control-product", snapshot=snapshots[1], title="ChatGPT Pro 5x 月卡")
    add_offer("unclassified", None, snapshot=snapshots[1], title="ChatGPT Pro 20x 月卡")
    db.commit()
    return {slug: product.id for slug, product in products.items()}


@pytest.mark.parametrize("canonical_visible", [None, True, False], ids=["legacy-only", "existing", "hidden"])
def test_pipeline_merge_moves_all_snapshots_without_touching_offer_or_audit_columns(
    merge_db, canonical_visible,
):
    db = merge_db
    original_ids = _seed_legacy_catalog(db, canonical_visible=canonical_visible)
    before_offers = _rows(db, Offer)
    untouched = {model: _rows(db, model) for model in (RawProduct, OfferHistory, CatalogSnapshot, Shop)}
    products = ensure_products(db)
    db.flush()
    replacements = {original_ids[legacy]: products[canonical].id for legacy, canonical in PLAN_PAIRS}
    assert _rows(db, Offer) == {
        offer_id: {**row, "product_id": replacements.get(row["product_id"], row["product_id"])}
        for offer_id, row in before_offers.items()
    }
    for legacy, canonical in PLAN_PAIRS:
        assert products[legacy].id == original_ids[legacy]
        assert products[legacy].is_visible is False
        assert products[canonical].is_visible is (canonical_visible is not False)
        if canonical_visible is not None:
            assert products[canonical].id == original_ids[canonical]
    for model, expected in untouched.items():
        assert _rows(db, model) == expected, model.__name__
    db.commit()
    after_first = {model: _rows(db, model) for model in (Product, Offer, *untouched)}
    ensure_products(db)
    db.flush()
    for model, expected in after_first.items():
        assert _rows(db, model) == expected, f"second merge changed {model.__name__}"


def test_pipeline_merge_leaves_commit_and_rollback_to_its_caller(merge_db):
    db = merge_db
    _seed_legacy_catalog(db, canonical_visible=None)
    models = (Product, Offer, RawProduct, OfferHistory, CatalogSnapshot, Shop)
    before = {model: _rows(db, model) for model in models}
    shop = db.scalar(select(Shop))
    shop.name = "uncommitted caller edit"
    products = ensure_products(db)
    db.flush()
    assert _rows(db, Offer) != before[Offer]
    assert all(products[canonical].id is not None for _, canonical in PLAN_PAIRS)
    db.rollback()
    for model, expected in before.items():
        assert _rows(db, model) == expected, f"rollback lost {model.__name__}"


@pytest.mark.parametrize(("title", "category", "canonical"), [
    ("ChatGPT Pro 5x 月卡", "", "chatgpt-pro-100"),
    ("ChatGPT Pro 5× 成品号", "OpenAI Pro 20x", "chatgpt-pro-100"),
    ("Codex Pro 5X 【保订阅~智利/埃及卡冲】支持续费（不支持升级菲区20x）", "OpenAI Pro 20x", "chatgpt-pro-100"),
    ("ChatGPT Pro 20x 订阅", "OpenAI Pro 5x", "chatgpt-pro-200"),
    ("Codex Pro 20倍 月卡", "", "chatgpt-pro-200"),
])
def test_pipeline_classifier_resolves_legacy_merchant_titles(title, category, canonical):
    assert classify(title, category).slug == canonical


@pytest.mark.parametrize(("legacy", "canonical"), PLAN_PAIRS)
def test_new_import_uses_canonical_product_and_retains_merchant_title(merge_db, legacy, canonical):
    db = merge_db
    products = ensure_products(db)
    snapshot = CatalogSnapshot(source="legacy-title-import")
    db.add(snapshot)
    db.flush()
    title = f"ChatGPT Pro {legacy.rsplit('-', 1)[-1]} 直充一个月"
    raw_json = {"description": f"<p>{title}，全程质保</p>", "original_tier": legacy}
    upsert_offer(db, {
        "token": "new-pro-shop", "shop_name": "Merchant", "shop_url": "https://example.com/shop",
        "product_key": "legacy-pro-sku", "product_name": title, "category_name": "OpenAI Pro",
        "product_url": "https://example.com/item", "listed_price": "123.45",
        "stock_count": 7, "product_status": "in_stock", "raw_json": raw_json,
    }, products, snapshot_id=snapshot.id)
    db.flush()
    offer = db.scalar(select(Offer))
    raw = db.get(RawProduct, offer.raw_product_id)
    assert offer.product_id == products[canonical].id
    assert offer.snapshot_id == snapshot.id
    assert raw.original_name == title
    assert raw.raw_json == raw_json
    assert products[legacy].is_visible is False
    before_offers = _rows(db, Offer)
    before_history = _rows(db, OfferHistory)
    ensure_products(db)
    db.flush()
    assert _rows(db, Offer) == before_offers
    assert _rows(db, OfferHistory) == before_history
