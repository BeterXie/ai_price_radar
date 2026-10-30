"""Regression contracts for merging legacy ChatGPT Pro catalog identities."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.database import Base, get_db
from app.main import app
from app.models import (
    CatalogSnapshot, CommunitySkill, Offer, OfferClick, OfferHistory, Product,
    RawProduct, Report, Shop, User, UserProductSubscription,
)
from app.security import require_current_user
from app.services.account_plans import canonical_product_slug, ensure_account_plans
from app.services.catalog import (
    OfferFilters, count_product_cards, get_catalog_group_page, get_group_offers,
    get_product_detail, get_product_history, get_product_offer_page, list_product_cards,
)
from app.services.classifier import classify_product


PLAN_PAIRS = (
    ("chatgpt-pro-5x", "chatgpt-pro-100"),
    ("chatgpt-pro-20x", "chatgpt-pro-200"),
)


@pytest.fixture
def merge_db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            yield db
    finally:
        engine.dispose()


@pytest.fixture
def merge_client(merge_db):
    previous_overrides = app.dependency_overrides.copy()

    def override_db():
        yield merge_db

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    try:
        yield client
    finally:
        client.close()
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


def _rows(db, model):
    """Read persisted columns, including fields not named in individual assertions."""
    return {
        row["id"]: deepcopy(dict(row))
        for row in db.execute(select(model.__table__).order_by(model.id)).mappings()
    }


def _seed_catalog(db, *, canonical_visible=True):
    """None means the installation has legacy products but no canonical rows yet."""
    now = datetime.now(timezone.utc).replace(microsecond=0)
    old = now - timedelta(days=10)
    shop = Shop(
        token="pro-merge-shop", name="Pro merge shop", platform="ldxp",
        source_url="https://example.com/shop/pro", source_score=90,
        first_seen_at=old, last_seen_at=now, last_success_at=now,
    )
    snapshots = [
        CatalogSnapshot(source="previous", published_at=old, offer_count=2, created_at=old),
        CatalogSnapshot(source="current", published_at=now, offer_count=4, created_at=now),
    ]
    products = {}
    for legacy, canonical in PLAN_PAIRS:
        products[legacy] = Product(slug=legacy, platform="OpenAI", display_name=legacy)
        if canonical_visible is not None:
            products[canonical] = Product(
                slug=canonical, platform="OpenAI", display_name=canonical,
                is_visible=canonical_visible,
            )
    products["control-product"] = Product(
        slug="control-product", platform="Other", display_name="Unrelated product",
    )
    db.add_all([shop, *snapshots, *products.values()])
    db.flush()
    offers = {}

    def add_offer(key, slug, price, *, snapshot, observed_at=now, manual=False, title=None):
        title = title or f"ChatGPT Pro {slug.rsplit('-', 1)[-1]} 月卡 原标题"
        raw = RawProduct(
            shop_id=shop.id, source_product_key=key, original_name=title,
            original_category="商家原分类 / Pro 5x / 20x",
            source_url=f"https://example.com/item/{key}",
            raw_json={"description": f"<p>{title}，原文不得重写</p>", "sku": {"key": key}},
            first_seen_at=old, last_seen_at=observed_at,
        )
        db.add(raw)
        db.flush()
        canonical = dict(PLAN_PAIRS).get(slug, slug)
        offer = Offer(
            raw_product_id=raw.id, product_id=products[slug].id if slug is not None else None,
            shop_id=shop.id, snapshot_id=snapshot.id if snapshot else None,
            price=Decimal(price), currency="CNY", stock_count=7, stock_status="in_stock",
            auto_delivery=True, tags=["manual_override", "保留标签"] if manual else ["月付"],
            risk_flags=["原始提示"], classification_confidence=100 if manual else 87,
            delivery_type="finished_account", is_comparable=True,
            service_period="one_month", warranty="first_login", use_scenarios=["coding"],
            item_fingerprint=f"group-{canonical}", source_url=raw.source_url,
            observed_at=observed_at, active=not manual, approved=not manual,
            hidden_reason="人工隐藏：保留审核决定" if manual else "",
            click_count=19, created_at=old, updated_at=old + timedelta(hours=1),
        )
        db.add(offer)
        db.flush()
        db.add(OfferHistory(
            offer_id=offer.id, price=Decimal(price) + Decimal("5.00"),
            currency="CNY", stock_count=3, stock_status="in_stock",
            observed_at=now - timedelta(days=1) if observed_at == now else old,
        ))
        offers[key] = offer.id

    for index, (legacy, canonical) in enumerate(PLAN_PAIRS):
        add_offer(f"{legacy}-public", legacy, str(110 + index * 100), snapshot=snapshots[1])
        add_offer(
            f"{legacy}-manual", legacy, "79.00", snapshot=snapshots[1], manual=True,
            title="人工指定分类：标题没有套餐名称",
        )
        add_offer(f"{legacy}-historical", legacy, "85.00", snapshot=snapshots[0], observed_at=old)
        add_offer(f"{legacy}-unpublished", legacy, "95.00", snapshot=None, observed_at=old)
        if canonical in products:
            add_offer(f"{canonical}-public", canonical, str(130 + index * 100), snapshot=snapshots[1])
    # The merge follows product_id, never a matching merchant title.
    add_offer("control", "control-product", "500.00", snapshot=snapshots[1], title="ChatGPT Pro 5x 月卡")
    add_offer("unclassified", None, "600.00", snapshot=snapshots[1], title="ChatGPT Pro 20x 月卡")
    db.commit()
    return {
        "product_ids": {slug: product.id for slug, product in products.items()},
        "offer_ids": offers, "snapshot_id": snapshots[1].id,
        "shop_id": shop.id, "old": old,
    }


def _seed_references(db, data, legacy, canonical, *, both=False):
    user = User(email="merge-subscriber@example.com", nickname="Merge subscriber")
    db.add(user)
    db.flush()
    old = data["old"]
    legacy_sub = UserProductSubscription(
        user_id=user.id, product_slug=legacy, target_price=Decimal("123.45"),
        notify_email=False, notify_bot=True, created_at=old, updated_at=old + timedelta(hours=1),
    )
    subscriptions = [legacy_sub]
    if both:
        subscriptions.append(UserProductSubscription(
            user_id=user.id, product_slug=canonical, target_price=None,
            notify_email=True, notify_bot=False,
            created_at=old + timedelta(hours=2), updated_at=old + timedelta(hours=3),
        ))
    skill = CommunitySkill(
        slug="pro-merge-guide", title="Pro 5x 商家名称说明", content_markdown="保留旧称 5x / 20x 原文",
        related_product_slug=legacy, is_visible=False, is_pinned=True, tags=["原标签"],
        created_at=old, updated_at=old,
    )
    offer_id = data["offer_ids"][f"{legacy}-public"]
    report = Report(
        offer_id=offer_id, product_slug=legacy, message="历史反馈保留旧套餐名与关联报价",
        status="resolved", public_summary="已核实", created_at=old, updated_at=old,
    )
    click = OfferClick(
        offer_id=offer_id, shop_id=data["shop_id"], user_id=user.id, product_slug=legacy,
        ip_hash="a" * 64, user_agent="historic-client", created_at=old,
    )
    db.add_all([*subscriptions, skill, report, click])
    db.commit()
    return user.id, legacy_sub.id, subscriptions[-1].id


@pytest.mark.parametrize("canonical_visible", [None, True, False], ids=["legacy-only", "existing", "hidden"])
def test_api_plan_merge_preserves_offer_identity_audit_fields_and_is_idempotent(merge_db, canonical_visible):
    db = merge_db
    data = _seed_catalog(db, canonical_visible=canonical_visible)
    before_offers = _rows(db, Offer)
    untouched = {model: _rows(db, model) for model in (RawProduct, OfferHistory, CatalogSnapshot, Shop)}
    ensure_account_plans(db)
    db.flush()
    products = {product.slug: product for product in db.scalars(select(Product))}
    old_to_new = {data["product_ids"][old]: products[new].id for old, new in PLAN_PAIRS}
    expected_offers = {
        offer_id: {**row, "product_id": old_to_new.get(row["product_id"], row["product_id"])}
        for offer_id, row in before_offers.items()
    }
    assert _rows(db, Offer) == expected_offers
    for legacy, canonical in PLAN_PAIRS:
        assert products[legacy].id == data["product_ids"][legacy]
        assert products[legacy].is_visible is False
        assert products[canonical].is_visible is (canonical_visible is not False)
        if canonical_visible is not None:
            assert products[canonical].id == data["product_ids"][canonical]
    for model, expected in untouched.items():
        assert _rows(db, model) == expected, model.__name__
    db.commit()
    after_first_merge = {model: _rows(db, model) for model in (Product, Offer, *untouched)}
    ensure_account_plans(db)
    db.flush()
    for model, expected in after_first_merge.items():
        assert _rows(db, model) == expected, f"second merge changed {model.__name__}"


@pytest.mark.parametrize(("legacy", "canonical"), PLAN_PAIRS)
@pytest.mark.parametrize("both", [False, True], ids=["legacy-only", "canonical-preferences-win"])
def test_subscription_merge_preserves_winning_row_and_skill_but_not_historical_slugs(
    merge_db, legacy, canonical, both,
):
    db = merge_db
    data = _seed_catalog(db)
    _, legacy_id, winner_id = _seed_references(db, data, legacy, canonical, both=both)
    expected_subscription = {**_rows(db, UserProductSubscription)[winner_id], "product_slug": canonical}
    expected_skill = {
        key: {**row, "related_product_slug": canonical}
        for key, row in _rows(db, CommunitySkill).items()
    }
    history = {model: _rows(db, model) for model in (Report, OfferClick)}
    for _ in range(2):
        ensure_account_plans(db)
        db.flush()
        assert _rows(db, UserProductSubscription) == {winner_id: expected_subscription}
        assert _rows(db, CommunitySkill) == expected_skill
        for model, expected in history.items():
            assert _rows(db, model) == expected
        if both:
            assert legacy_id not in _rows(db, UserProductSubscription)
        db.commit()


def test_api_plan_merge_is_owned_by_the_callers_transaction(merge_db):
    db = merge_db
    data = _seed_catalog(db, canonical_visible=None)
    legacy, canonical = PLAN_PAIRS[0]
    _seed_references(db, data, legacy, canonical)
    models = (Product, Offer, RawProduct, OfferHistory, CatalogSnapshot, Shop,
              UserProductSubscription, CommunitySkill, Report, OfferClick)
    before = {model: _rows(db, model) for model in models}
    db.get(Shop, data["shop_id"]).name = "uncommitted caller edit"
    ensure_account_plans(db)
    db.flush()
    assert db.scalar(select(UserProductSubscription.product_slug)) == canonical
    assert _rows(db, Offer) != before[Offer]
    assert db.scalar(select(Product.id).where(Product.slug == canonical)) is not None
    db.rollback()
    for model, expected in before.items():
        assert _rows(db, model) == expected, f"rollback lost {model.__name__}"


@pytest.mark.parametrize(("value", "expected"), [
    ("chatgpt-pro-5x", "chatgpt-pro-100"),
    ("  CHATGPT-PRO-20X  ", "chatgpt-pro-200"),
    ("chatgpt-pro-100", "chatgpt-pro-100"),
    ("chatgpt-pro-200", "chatgpt-pro-200"),
    ("claude-pro-20x", "claude-pro-20x"),
    ("", ""),
])
def test_canonical_plan_slug_resolves_only_chatgpt_aliases(value, expected):
    assert canonical_product_slug(value) == expected


@pytest.mark.parametrize(("title", "category", "expected"), [
    ("ChatGPT Pro 5x 月卡", "", "chatgpt-pro-100"),
    ("ChatGPT Pro 5× 成品号", "OpenAI Pro 20x", "chatgpt-pro-100"),
    ("Codex Pro 5X 【保订阅~智利/埃及卡冲】支持续费（不支持升级菲区20x）", "OpenAI Pro 20x", "chatgpt-pro-100"),
    ("ChatGPT Pro 20x 订阅", "OpenAI Pro 5x", "chatgpt-pro-200"),
    ("Codex Pro 20倍 月卡", "", "chatgpt-pro-200"),
    ("ChatGPT Pro 100 月卡", "OpenAI Pro 20x", "chatgpt-pro-100"),
    ("ChatGPT Pro $200 月卡", "OpenAI Pro 5x", "chatgpt-pro-200"),
])
def test_classifier_emits_canonical_plan_for_legacy_merchant_titles(title, category, expected):
    assert classify_product(title, category).slug == expected


@pytest.fixture
def merged_catalog(merge_db):
    data = _seed_catalog(merge_db)
    ensure_account_plans(merge_db)
    merge_db.commit()
    return data


@pytest.mark.parametrize(("legacy", "canonical"), PLAN_PAIRS)
def test_catalog_service_entry_points_resolve_legacy_slugs(merge_db, merged_catalog, legacy, canonical):
    db = merge_db
    snapshot_id = merged_catalog["snapshot_id"]
    detail = get_product_detail(db, legacy, snapshot_id=snapshot_id)
    assert detail == get_product_detail(db, canonical, snapshot_id=snapshot_id)
    assert detail.slug == canonical
    assert detail.offer_count == 2
    history = get_product_history(db, legacy)
    assert history == get_product_history(db, canonical)
    assert history.trend
    offers = get_product_offer_page(db, legacy, offset=0, limit=30, snapshot_id=snapshot_id)
    assert offers == get_product_offer_page(db, canonical, offset=0, limit=30, snapshot_id=snapshot_id)
    assert {item.id for item in offers} == {
        merged_catalog["offer_ids"][f"{legacy}-public"],
        merged_catalog["offer_ids"][f"{canonical}-public"],
    }
    grouped = get_group_offers(db, legacy, f"group-{canonical}", snapshot_id=snapshot_id)
    assert grouped == get_group_offers(db, canonical, f"group-{canonical}", snapshot_id=snapshot_id)
    assert len(grouped) == 2
    for filters in (OfferFilters(), OfferFilters(max_price=Decimal("120.00" if canonical.endswith("100") else "220.00"))):
        for argument in ("product_slug", "product_slugs"):
            old_value = legacy if argument == "product_slug" else (legacy, canonical, legacy)
            new_value = canonical if argument == "product_slug" else (canonical,)
            old_args = {argument: old_value, "filters": filters, "snapshot_id": snapshot_id}
            new_args = {argument: new_value, "filters": filters, "snapshot_id": snapshot_id}
            cards = list_product_cards(db, **old_args)
            assert cards == list_product_cards(db, **new_args)
            assert [card.slug for card in cards] == [canonical]
            assert count_product_cards(db, **old_args) == count_product_cards(db, **new_args) == 1
        old_groups = get_catalog_group_page(db, product_slug=legacy, offset=0, limit=30, filters=filters)
        new_groups = get_catalog_group_page(db, product_slug=canonical, offset=0, limit=30, filters=filters)
        assert old_groups == new_groups
        assert old_groups[1] == 1


@pytest.mark.parametrize(("legacy", "canonical"), PLAN_PAIRS)
@pytest.mark.parametrize("suffix", ["", "/offers", "/history", "/groups", "/groups/{fingerprint}"])
def test_public_legacy_urls_return_canonical_content_without_redirects(
    merge_client, merged_catalog, legacy, canonical, suffix,
):
    suffix = suffix.format(fingerprint=f"group-{canonical}")
    old = merge_client.get(f"/api/v1/products/{legacy}{suffix}", follow_redirects=False)
    new = merge_client.get(f"/api/v1/products/{canonical}{suffix}", follow_redirects=False)
    assert old.status_code == new.status_code == 200, (old.text, new.text)
    assert "location" not in old.headers
    assert old.json() == new.json()
    payload = old.json()
    if not suffix:
        assert payload["slug"] == canonical
        assert payload["offer_count"] == 2
    elif suffix == "/history":
        assert payload["trend"]
    elif suffix == "/groups":
        assert payload["total"] == 1
        assert payload["offer_total"] == 2
        assert payload["items"][0]["product_slug"] == canonical
    else:
        assert len(payload["items"]) == 2


@pytest.mark.parametrize(("legacy", "canonical"), PLAN_PAIRS)
@pytest.mark.parametrize("filtered", [False, True])
def test_public_catalog_single_batch_and_group_filters_resolve_aliases(
    merge_client, merged_catalog, legacy, canonical, filtered,
):
    params = {"max_price": "120" if canonical.endswith("100") else "220"} if filtered else {}
    for key in ("product", "products"):
        old_value = legacy if key == "product" else f"{legacy},{canonical},{legacy}"
        old = merge_client.get("/api/v1/products", params={**params, key: old_value})
        new = merge_client.get("/api/v1/products", params={**params, key: canonical})
        assert old.status_code == new.status_code == 200
        assert old.json() == new.json()
        assert old.json()["total"] == 1
        assert [item["slug"] for item in old.json()["items"]] == [canonical]
        assert old.json()["offer_count"] == (1 if filtered else 2)
    old = merge_client.get("/api/v1/catalog/groups", params={**params, "product": legacy})
    new = merge_client.get("/api/v1/catalog/groups", params={**params, "product": canonical})
    assert old.status_code == new.status_code == 200
    assert old.json() == new.json()
    assert old.json()["total"] == 1
    assert old.json()["offer_total"] == (1 if filtered else 2)


def test_public_batch_deduplicates_both_alias_pairs(merge_client, merged_catalog):
    aliases = ",".join(slug for pair in PLAN_PAIRS for slug in pair)
    canonical_slugs = ",".join(canonical for _, canonical in PLAN_PAIRS)
    old = merge_client.get("/api/v1/products", params={"products": aliases})
    new = merge_client.get("/api/v1/products", params={"products": canonical_slugs})
    assert old.status_code == new.status_code == 200
    assert old.json() == new.json()
    assert old.json()["total"] == 2
    assert old.json()["offer_count"] == 4


@pytest.mark.parametrize(("legacy", "canonical"), PLAN_PAIRS)
def test_zero_offer_card_fallback_and_filters_treat_alias_as_canonical(
    merge_db, merge_client, merged_catalog, legacy, canonical,
):
    product_id = merged_catalog["product_ids"][canonical]
    for offer in merge_db.scalars(select(Offer).where(Offer.product_id == product_id)):
        offer.active = False
    merge_db.commit()
    for key in ("product", "products"):
        for filtered in (False, True):
            extra = {"in_stock": "true"} if filtered else {}
            old = merge_client.get("/api/v1/products", params={key: legacy, **extra})
            new = merge_client.get("/api/v1/products", params={key: canonical, **extra})
            assert old.status_code == new.status_code == 200
            assert old.json() == new.json()
            assert old.json()["total"] == (0 if filtered else 1)
            assert old.json()["offer_count"] == 0


@pytest.mark.parametrize(("legacy", "canonical"), PLAN_PAIRS)
def test_alias_never_reveals_a_hidden_canonical_product(merge_db, merge_client, legacy, canonical):
    _seed_catalog(merge_db, canonical_visible=False)
    ensure_account_plans(merge_db)
    merge_db.commit()
    for suffix in ("", "/offers", "/history", "/groups", f"/groups/group-{canonical}"):
        for slug in (legacy, canonical):
            response = merge_client.get(f"/api/v1/products/{slug}{suffix}", follow_redirects=False)
            assert response.status_code == 404
    for key in ("product", "products"):
        response = merge_client.get("/api/v1/products", params={key: legacy})
        assert response.status_code == 200
        assert response.json()["items"] == []
        assert response.json()["total"] == 0


@pytest.mark.parametrize(("legacy", "canonical"), PLAN_PAIRS)
def test_new_report_accepts_legacy_slug_with_migrated_offer(
    merge_db, merge_client, merged_catalog, monkeypatch, legacy, canonical,
):
    monkeypatch.setattr(get_settings(), "report_rate_limit_count", 10)
    offer_id = merged_catalog["offer_ids"][f"{legacy}-public"]
    response = merge_client.post("/api/v1/reports", json={
        "kind": "correction", "message": "旧链接的报价与商家原始页面价格不一致", "product_slug": legacy,
        "offer_id": offer_id,
    })
    assert response.status_code == 201, response.text
    report = merge_db.get(Report, response.json()["id"])
    assert report.product_slug == canonical
    assert report.offer_id == offer_id
    mismatch = merge_client.post("/api/v1/reports", json={
        "kind": "correction", "message": "另一商品报价仍应受到归属校验", "product_slug": legacy,
        "offer_id": merged_catalog["offer_ids"]["control"],
    })
    assert mismatch.status_code == 422
    assert len(_rows(merge_db, Report)) == 1


@pytest.mark.parametrize(("legacy", "canonical"), PLAN_PAIRS)
def test_subscription_create_update_patch_and_delete_accept_legacy_slug(
    merge_db, merge_client, merged_catalog, legacy, canonical,
):
    user = User(email="crud-subscriber@example.com", nickname="Subscriber")
    merge_db.add(user)
    merge_db.commit()
    app.dependency_overrides[require_current_user] = lambda: user
    payload = {"product_slug": legacy, "target_price": "135.00", "notify_email": False, "notify_bot": True}
    created = merge_client.post("/api/v1/user/subscriptions", json=payload)
    assert created.status_code == 200, created.text
    assert created.json()["product_slug"] == canonical
    subscription_id = created.json()["id"]
    updated = merge_client.post("/api/v1/user/subscriptions", json={**payload, "product_slug": canonical, "target_price": "125.00"})
    assert updated.status_code == 200
    assert updated.json()["id"] == subscription_id
    patched = merge_client.patch(f"/api/v1/user/subscriptions/{legacy}", json={"notify_bot": False})
    assert patched.status_code == 200, patched.text
    assert patched.json()["id"] == subscription_id
    assert patched.json()["product_slug"] == canonical
    assert patched.json()["target_price"] == "125.00"
    assert patched.json()["notify_email"] is False
    assert patched.json()["notify_bot"] is False
    listed = merge_client.get("/api/v1/user/subscriptions")
    assert listed.status_code == 200
    assert listed.json()["count"] == 1
    assert listed.json()["items"][0]["product_slug"] == canonical
    assert len(_rows(merge_db, UserProductSubscription)) == 1
    deleted = merge_client.delete(f"/api/v1/user/subscriptions/{legacy}")
    assert deleted.status_code == 200
    assert deleted.json()["success"] is True
    assert _rows(merge_db, UserProductSubscription) == {}


@pytest.mark.parametrize(("legacy", "canonical"), PLAN_PAIRS)
def test_admin_offer_assignment_and_product_filter_accept_legacy_slug(
    merge_db, merge_client, merged_catalog, monkeypatch, legacy, canonical,
):
    monkeypatch.setattr(get_settings(), "admin_api_key", "pro-merge-admin-test")
    headers = {"X-Admin-Key": "pro-merge-admin-test"}
    offer_id = merged_catalog["offer_ids"]["control"]
    response = merge_client.patch(
        f"/api/v1/admin/offers/{offer_id}", json={"product_slug": legacy}, headers=headers,
    )
    assert response.status_code == 200, response.text
    merge_db.expire_all()
    offer = merge_db.get(Offer, offer_id)
    assert offer.product_id == merged_catalog["product_ids"][canonical]
    assert "manual_override" in offer.tags
    old = merge_client.get("/api/v1/admin/offers", params={"product_slug": legacy}, headers=headers)
    new = merge_client.get("/api/v1/admin/offers", params={"product_slug": canonical}, headers=headers)
    assert old.status_code == new.status_code == 200
    assert old.json() == new.json()
    assert offer_id in {item["id"] for item in old.json()}


@pytest.mark.parametrize(("legacy", "canonical"), PLAN_PAIRS)
def test_community_skill_create_update_and_public_detail_accept_legacy_link_after_merge(
    merge_db, merge_client, merged_catalog, monkeypatch, legacy, canonical,
):
    monkeypatch.setattr(get_settings(), "admin_api_key", "pro-merge-admin-test")
    headers = {"X-Admin-Key": "pro-merge-admin-test"}
    assert merge_db.get(Product, merged_catalog["product_ids"][legacy]).is_visible is False
    skill_slug = f"guide-{legacy}"
    markdown = f"# 商家原文\n本教程中的 {legacy} 旧称应保留。"
    created = merge_client.post("/api/v1/admin/skills", headers=headers, json={
        "slug": skill_slug, "kind": "article", "title": f"{legacy} 使用说明",
        "content_markdown": markdown, "related_product_slug": legacy, "is_visible": True,
    })
    assert created.status_code == 200, created.text
    assert created.json()["related_product_slug"] == canonical
    skill_id = created.json()["id"]
    merge_db.expire_all()
    skill = merge_db.get(CommunitySkill, skill_id)
    assert skill.related_product_slug == canonical

    def assert_public_link(title):
        detail = merge_client.get(f"/api/v1/skills/{skill_slug}")
        assert detail.status_code == 200, detail.text
        payload = detail.json()
        assert payload["id"] == skill_id
        assert payload["title"] == title
        assert payload["content_markdown"] == markdown
        assert payload["related_product_slug"] == canonical
        assert payload["related_product"]["slug"] == canonical
        assert payload["related_product"]["display_name"] == merge_db.get(
            Product, merged_catalog["product_ids"][canonical],
        ).display_name

    assert_public_link(f"{legacy} 使用说明")
    # An older writer can leave an alias after the one-time merge has finished.
    skill.related_product_slug = legacy
    merge_db.commit()
    assert_public_link(f"{legacy} 使用说明")

    updated = merge_client.put(f"/api/v1/admin/skills/{skill_id}", headers=headers, json={
        "related_product_slug": legacy, "title": f"{legacy} 编辑后的使用说明",
    })
    assert updated.status_code == 200, updated.text
    assert updated.json()["id"] == skill_id
    assert updated.json()["related_product_slug"] == canonical
    merge_db.expire_all()
    assert merge_db.get(CommunitySkill, skill_id).related_product_slug == canonical
    assert_public_link(f"{legacy} 编辑后的使用说明")
