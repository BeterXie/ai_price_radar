from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import text

from common import CatalogSnapshot, Offer, begin_snapshot, ensure_products, session_for
from connectors import CONNECTORS
from publish_catalog import (
    SourceImportError,
    SourceSpec,
    UNREVIEWED_DUJIAO_ENV,
    approved_dujiao_sources,
    approved_intake_sources,
    import_source_into_snapshot,
    publish_sources,
    validate_dujiao_source_access,
)


def record(source: str) -> dict:
    return {
        "token": f"shop-{source}",
        "shop_name": f"Shop {source}",
        "shop_url": f"https://{source}.example",
        "source_platform": "merchant_json",
        "product_key": f"product-{source}",
        "product_name": f"ChatGPT Plus {source} 直充一个月",
        "product_url": f"https://{source}.example/product",
        "listed_price": "88.00",
        "currency": "CNY",
        "stock_count": 1,
        "product_status": "in_stock",
    }


def install_loader(monkeypatch: pytest.MonkeyPatch, *, failing_source: str | None = None) -> None:
    def loader(source: str | Path):
        value = str(source)
        if value == failing_source:
            raise ValueError("upstream unavailable")
        yield record(value)

    monkeypatch.setitem(CONNECTORS, "merchant-json", loader)


def create_review_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE dujiao_candidates (
                origin TEXT PRIMARY KEY,
                api_verified INTEGER NOT NULL,
                status TEXT NOT NULL,
                review_status TEXT NOT NULL
            )
            """
        )
        conn.executemany(
            "INSERT INTO dujiao_candidates(origin, api_verified, status, review_status) VALUES (?, ?, ?, ?)",
            [
                ("https://approved.example", 1, "pending_review", "approved"),
                ("https://future.example", 1, "verified", "approved"),
                ("https://stale.example", 0, "validation_failed", "approved"),
                ("https://rejected.example", 1, "pending_review", "rejected"),
            ],
        )


def create_source_intakes(db) -> None:
    db.execute(text(
        "CREATE TABLE source_intakes ("
        "id INTEGER PRIMARY KEY, source_type TEXT NOT NULL, detected_platform TEXT NOT NULL, "
        "source_url TEXT NOT NULL, status TEXT NOT NULL, product_count INTEGER NOT NULL DEFAULT 0, "
        "finished_at TEXT, updated_at TEXT)"
    ))
    db.commit()


def test_multiple_sources_share_one_published_snapshot(monkeypatch: pytest.MonkeyPatch):
    install_loader(monkeypatch)
    db = session_for("sqlite://")
    try:
        result = publish_sources(
            db,
            [SourceSpec("merchant-json", "a"), SourceSpec("merchant-json", "b")],
        )

        offers = db.query(Offer).order_by(Offer.id).all()
        snapshots = db.query(CatalogSnapshot).filter(CatalogSnapshot.published_at.isnot(None)).all()
        assert result.offer_count == 2
        assert [offer.snapshot_id for offer in offers] == [result.snapshot_id, result.snapshot_id]
        assert [snapshot.id for snapshot in snapshots] == [result.snapshot_id]
    finally:
        db.close()


def test_source_failure_keeps_previous_current_snapshot_and_removes_draft(monkeypatch: pytest.MonkeyPatch):
    install_loader(monkeypatch)
    db = session_for("sqlite://")
    try:
        previous = publish_sources(db, [SourceSpec("merchant-json", "a")])
        install_loader(monkeypatch, failing_source="b")

        with pytest.raises(SourceImportError, match="upstream unavailable"):
            publish_sources(
                db,
                [SourceSpec("merchant-json", "a"), SourceSpec("merchant-json", "b")],
            )

        snapshots = db.query(CatalogSnapshot).all()
        offer = db.query(Offer).one()
        assert [(snapshot.id, snapshot.published_at is not None) for snapshot in snapshots] == [(previous.snapshot_id, True)]
        assert offer.snapshot_id == previous.snapshot_id
    finally:
        db.close()


def test_single_source_import_targets_draft_without_publishing(monkeypatch: pytest.MonkeyPatch):
    install_loader(monkeypatch)
    db = session_for("sqlite://")
    try:
        products = ensure_products(db)
        snapshot = begin_snapshot(db, "draft")
        result = import_source_into_snapshot(
            db,
            connector="merchant-json",
            source="a",
            snapshot_id=snapshot.id,
            products=products,
        )

        assert result.total == 1
        assert db.query(Offer).one().snapshot_id == snapshot.id
        assert snapshot.published_at is None
        assert db.query(CatalogSnapshot).filter(CatalogSnapshot.published_at.isnot(None)).count() == 0
    finally:
        db.rollback()
        db.close()


def test_approved_dujiao_sources_require_current_api_verification(tmp_path: Path):
    review_db = tmp_path / "discovery.db"
    create_review_db(review_db)

    assert approved_dujiao_sources(review_db) == [
        "https://approved.example",
        "https://future.example",
    ]
    validate_dujiao_source_access(
        "https://approved.example/",
        review_db=review_db,
        allow_unreviewed=False,
    )
    with pytest.raises(ValueError, match="not approved"):
        validate_dujiao_source_access(
            "https://stale.example",
            review_db=review_db,
            allow_unreviewed=False,
        )


def test_approved_dujiao_sources_can_enter_atomic_publish(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    review_db = tmp_path / "discovery.db"
    create_review_db(review_db)

    def loader(source: str | Path):
        value = str(source).removeprefix("https://").split(".", 1)[0]
        item = record(value)
        item["source_platform"] = "dujiao_next"
        yield item

    monkeypatch.setitem(CONNECTORS, "dujiao-next", loader)
    db = session_for("sqlite://")
    try:
        result = publish_sources(
            db,
            [SourceSpec("dujiao-next", source) for source in approved_dujiao_sources(review_db)],
        )

        assert result.offer_count == 2
        assert db.query(Offer).filter(Offer.snapshot_id == result.snapshot_id).count() == 2
    finally:
        db.close()


def test_unreviewed_dujiao_bypass_requires_flag_and_environment_gate():
    source = "https://development.example"
    with pytest.raises(ValueError, match="not approved"):
        validate_dujiao_source_access(
            source,
            review_db=None,
            allow_unreviewed=False,
            environ={UNREVIEWED_DUJIAO_ENV: "1"},
        )
    with pytest.raises(ValueError, match=UNREVIEWED_DUJIAO_ENV):
        validate_dujiao_source_access(
            source,
            review_db=None,
            allow_unreviewed=True,
            environ={},
        )
    validate_dujiao_source_access(
        source,
        review_db=None,
        allow_unreviewed=True,
        environ={UNREVIEWED_DUJIAO_ENV: "1"},
    )


def test_compatibility_publish_carries_forward_other_sources(monkeypatch: pytest.MonkeyPatch):
    install_loader(monkeypatch)
    db = session_for("sqlite://")
    try:
        first = publish_sources(
            db,
            [SourceSpec("merchant-json", "a")],
            carry_forward_current=True,
        )
        second = publish_sources(
            db,
            [SourceSpec("merchant-json", "b")],
            carry_forward_current=True,
        )

        assert first.snapshot_id != second.snapshot_id
        assert db.query(Offer).filter(Offer.snapshot_id == second.snapshot_id).count() == 2
    finally:
        db.close()


def test_dry_run_does_not_publish_or_change_current_snapshot(monkeypatch: pytest.MonkeyPatch):
    install_loader(monkeypatch)
    db = session_for("sqlite://")
    try:
        previous = publish_sources(db, [SourceSpec("merchant-json", "a")])
        publish_sources(
            db,
            [SourceSpec("merchant-json", "b")],
            carry_forward_current=True,
            dry_run=True,
        )

        assert db.query(CatalogSnapshot).count() == 1
        assert db.query(Offer).one().snapshot_id == previous.snapshot_id
    finally:
        db.close()


def test_approved_dujiao_intake_publishes_atomically_and_becomes_published(monkeypatch: pytest.MonkeyPatch):
    def loader(source: str | Path):
        item = record("approved-dujiao")
        item["source_platform"] = "dujiao_next"
        item["shop_url"] = str(source)
        yield item

    monkeypatch.setitem(CONNECTORS, "dujiao-next", loader)
    db = session_for("sqlite://")
    try:
        create_source_intakes(db)
        db.execute(text(
            "INSERT INTO source_intakes(id, source_type, detected_platform, source_url, status) "
            "VALUES (1, 'dujiao_next', 'dujiao_next', 'https://approved.example', 'approved')"
        ))
        db.commit()

        sources = approved_intake_sources(db)
        assert sources == [SourceSpec("dujiao-next", "https://approved.example", (1,))]
        result = publish_sources(db, sources)

        row = db.execute(text("SELECT status, product_count FROM source_intakes WHERE id=1")).one()
        assert row == ("published", 1)
        assert db.query(Offer).filter(Offer.snapshot_id == result.snapshot_id).count() == 1
    finally:
        db.close()


def test_all_structured_intake_platforms_use_the_atomic_publish_path():
    db = session_for("sqlite://")
    try:
        create_source_intakes(db)
        db.execute(text(
            "INSERT INTO source_intakes(id, source_type, detected_platform, source_url, status) VALUES "
            "(1, 'woocommerce', 'woocommerce', 'https://woo.example', 'approved'), "
            "(2, 'schema_org', 'schema_org', 'https://structured.example', 'published'), "
            "(3, 'schema_org', 'other', 'https://mismatch.example', 'approved'), "
            "(4, 'woocommerce', 'woocommerce', 'https://disabled.example', 'disabled')"
        ))
        db.commit()

        assert approved_intake_sources(db) == [
            SourceSpec("woocommerce-store", "https://woo.example", (1,)),
            SourceSpec("schema-org", "https://structured.example", (2,)),
        ]
    finally:
        db.close()


def test_direct_sitemap_intake_keeps_exact_path_through_atomic_publish(
    monkeypatch: pytest.MonkeyPatch,
):
    sitemap_url = "https://structured.example/product-sitemap.xml"
    called_with: list[str] = []

    def loader(source: str | Path):
        called_with.append(str(source))
        item = record("direct-sitemap")
        item["source_platform"] = "schema_org"
        item["shop_url"] = "https://structured.example"
        yield item

    monkeypatch.setitem(CONNECTORS, "schema-org", loader)
    db = session_for("sqlite://")
    try:
        create_source_intakes(db)
        db.execute(text(
            "INSERT INTO source_intakes(id, source_type, detected_platform, source_url, status) "
            "VALUES (1, 'schema_org', 'schema_org', :source_url, 'approved')"
        ), {"source_url": sitemap_url})
        db.commit()

        sources = approved_intake_sources(db)
        assert sources == [SourceSpec("schema-org", sitemap_url, (1,))]
        result = publish_sources(db, sources)

        assert called_with == [sitemap_url]
        row = db.execute(text("SELECT status FROM source_intakes WHERE id=1")).one()
        assert row == ("published",)
        assert db.query(Offer).filter(Offer.snapshot_id == result.snapshot_id).count() == 1
    finally:
        db.close()


def test_published_intake_remains_in_later_snapshots_until_disabled(monkeypatch: pytest.MonkeyPatch):
    def loader(source: str | Path):
        label = "replacement" if "replacement" in str(source) else "persistent-dujiao"
        item = record(label)
        item["source_platform"] = "dujiao_next"
        item["shop_url"] = str(source)
        yield item

    monkeypatch.setitem(CONNECTORS, "dujiao-next", loader)
    db = session_for("sqlite://")
    try:
        create_source_intakes(db)
        db.execute(text(
            "INSERT INTO source_intakes(id, source_type, detected_platform, source_url, status) "
            "VALUES (1, 'dujiao_next', 'dujiao_next', 'https://persistent.example', 'approved')"
        ))
        db.commit()

        first = publish_sources(db, approved_intake_sources(db))
        assert db.execute(text("SELECT status FROM source_intakes WHERE id=1")).scalar_one() == "published"

        second_sources = approved_intake_sources(db)
        assert second_sources == [SourceSpec("dujiao-next", "https://persistent.example", (1,))]
        second = publish_sources(db, second_sources)
        assert second.snapshot_id != first.snapshot_id
        assert db.query(Offer).filter(Offer.snapshot_id == second.snapshot_id).count() == 1

        db.execute(text("UPDATE source_intakes SET status='disabled' WHERE id=1"))
        db.commit()
        assert approved_intake_sources(db) == []
        third = publish_sources(db, [SourceSpec("dujiao-next", "https://replacement.example")])
        current_tokens = {
            token for (token,) in db.execute(text(
                "SELECT shops.token FROM offers JOIN shops ON shops.id=offers.shop_id "
                "WHERE offers.snapshot_id=:snapshot_id"
            ), {"snapshot_id": third.snapshot_id})
        }
        assert current_tokens == {"shop-replacement"}
        assert db.query(Offer).filter(Offer.snapshot_id == third.snapshot_id).count() == 1
    finally:
        db.close()


def test_intake_requires_a_public_offer_before_becoming_published(monkeypatch: pytest.MonkeyPatch):
    def loader(_source: str | Path):
        item = record("unclassified")
        item["product_name"] = "Generic hosting support service"
        item["category_name"] = "Other"
        yield item

    monkeypatch.setitem(CONNECTORS, "merchant-json", loader)
    db = session_for("sqlite://")
    try:
        create_source_intakes(db)
        db.execute(text(
            "INSERT INTO source_intakes(id, source_type, detected_platform, source_url, status) "
            "VALUES (1, 'merchant_json', 'merchant_json', 'https://feed.example/catalog.json', 'approved')"
        ))
        db.commit()

        result = publish_sources(db, approved_intake_sources(db))

        imported = result.imports[0]
        assert (imported.raw_record_count, imported.classified_offer_count, imported.public_offer_count) == (1, 0, 0)
        assert db.execute(text("SELECT status, product_count FROM source_intakes WHERE id=1")).one() == (
            "no_products",
            0,
        )
    finally:
        db.close()


def test_public_offer_count_is_scoped_to_the_intake_import(monkeypatch: pytest.MonkeyPatch):
    def loader(source: str | Path):
        item = record(str(source))
        item["token"] = "shared-shop"
        if str(source) == "unclassified":
            item["product_name"] = "Generic hosting support service"
            item["category_name"] = "Other"
        yield item

    monkeypatch.setitem(CONNECTORS, "merchant-json", loader)
    db = session_for("sqlite://")
    try:
        create_source_intakes(db)
        db.execute(text(
            "INSERT INTO source_intakes(id, source_type, detected_platform, source_url, status) "
            "VALUES (1, 'merchant_json', 'merchant_json', 'unclassified', 'approved')"
        ))
        db.commit()

        sources = [SourceSpec("merchant-json", "public"), *approved_intake_sources(db)]
        result = publish_sources(db, sources)

        assert result.imports[0].public_offer_count == 1
        assert result.imports[1].public_offer_count == 0
        assert db.execute(text("SELECT status FROM source_intakes WHERE id=1")).scalar_one() == "no_products"
    finally:
        db.close()


def test_approved_dujiao_intake_requires_a_successful_live_import(monkeypatch: pytest.MonkeyPatch):
    def unavailable_loader(_source: str | Path):
        raise ValueError("Dujiao public API validation failed")
        yield

    monkeypatch.setitem(CONNECTORS, "dujiao-next", unavailable_loader)
    db = session_for("sqlite://")
    try:
        create_source_intakes(db)
        db.execute(text(
            "INSERT INTO source_intakes(id, source_type, detected_platform, source_url, status) "
            "VALUES (1, 'dujiao_next', 'dujiao_next', 'https://approved.example', 'approved')"
        ))
        db.commit()

        with pytest.raises(SourceImportError, match="public API validation failed"):
            publish_sources(db, approved_intake_sources(db))

        assert db.execute(text("SELECT status FROM source_intakes WHERE id=1")).scalar_one() == "approved"
        assert db.query(CatalogSnapshot).count() == 0
    finally:
        db.close()


def test_approved_intake_stays_approved_when_atomic_publish_fails(monkeypatch: pytest.MonkeyPatch):
    install_loader(monkeypatch, failing_source="https://feed.example/catalog.json")
    db = session_for("sqlite://")
    try:
        create_source_intakes(db)
        db.execute(text(
            "INSERT INTO source_intakes(id, source_type, detected_platform, source_url, status) "
            "VALUES (1, 'merchant_json', 'merchant_json', 'https://feed.example/catalog.json', 'approved')"
        ))
        db.commit()

        with pytest.raises(SourceImportError):
            publish_sources(db, approved_intake_sources(db))

        assert db.execute(text("SELECT status FROM source_intakes WHERE id=1")).scalar_one() == "approved"
        assert db.query(CatalogSnapshot).count() == 0
    finally:
        db.close()
