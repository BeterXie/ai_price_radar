"""Keep public reads proportional to the returned details, not merchant payload size."""
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, event, text, update
from sqlalchemy.orm import Session

from app.database import Base
from app.models import CatalogSnapshot, Offer, Product, RawProduct, Shop
from app.services.catalog import (
    OfferFilters,
    get_product_detail,
    get_product_group_page,
    get_product_offer_page,
    list_product_cards,
)


@pytest.fixture
def large_catalog():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    now = datetime.now(timezone.utc)
    with Session(engine) as db:
        snapshot = CatalogSnapshot(source='memory-test', published_at=now)
        shop = Shop(token='memory-shop', name='Shop', source_url='https://example.com')
        product = Product(slug='memory-product', platform='OpenAI', display_name='Product')
        db.add_all([snapshot, shop, product])
        db.flush()
        for index in range(160):
            raw = RawProduct(
                shop_id=shop.id, source_product_key=str(index), original_name=f'Quote {index}',
                raw_json={'description': '<p>' + 'description ' * 800 + '</p>'},
            )
            db.add(raw)
            db.flush()
            db.add(Offer(
                raw_product_id=raw.id, product_id=product.id, shop_id=shop.id,
                snapshot_id=snapshot.id, price=Decimal('1' if index == 0 else '100'),
                currency='CNY', stock_status='in_stock', is_comparable=True,
                delivery_type='finished_account', item_fingerprint=f'item-{index}',
                tags=['account'], observed_at=now, source_url='https://example.com/item',
            ))
        db.commit()
        product_id, snapshot_id = product.id, snapshot.id
    yield engine, product_id, snapshot_id
    engine.dispose()


@pytest.mark.parametrize('endpoint,detail_limit', [
    ('offers', 7), ('groups', 7), ('detail', 30), ('cards', 0),
])
def test_catalog_reads_bound_materialized_offer_details(large_catalog, endpoint, detail_limit):
    engine, product_id, snapshot_id = large_catalog
    loaded = Counter()
    with Session(engine) as db:
        event.listen(db, 'loaded_as_persistent', lambda _db, obj: loaded.update([type(obj).__name__]))
        if endpoint == 'offers':
            result = get_product_offer_page(db, 'memory-product', offset=7, limit=7, snapshot_id=snapshot_id)
            assert len(result) == 7
        elif endpoint == 'groups':
            result, groups, offers = get_product_group_page(db, product_id, offset=7, limit=7, filters=OfferFilters())
            assert len(result) == 7 and groups == offers == 160
        elif endpoint == 'detail':
            result = get_product_detail(db, 'memory-product', snapshot_id=snapshot_id)
            assert result.offer_count == 160 and len(result.offer_groups) == 30
            assert result.lowest_price == Decimal('100')
        else:
            result = list_product_cards(db, limit=24, snapshot_id=snapshot_id)
            assert len(result) == 1 and result[0].offer_count == 160
            assert result[0].trusted_offer_count == 159
        assert loaded['RawProduct'] <= detail_limit
        assert loaded['Offer'] <= detail_limit


def test_page_trust_uses_prices_beyond_the_page_and_keeps_all_details(large_catalog):
    engine, _, snapshot_id = large_catalog
    with Session(engine) as db:
        page = get_product_offer_page(db, 'memory-product', offset=0, limit=1, snapshot_id=snapshot_id)
        assert len(page) == 1
        assert page[0].price == Decimal('1')
        assert not page[0].is_trusted_price
        assert page[0].original_name == 'Quote 0'
        assert page[0].description_available
        assert page[0].original_description == ''  # Full text remains available through its existing endpoint.
        assert get_product_offer_page(db, 'memory-product', offset=160, limit=30, snapshot_id=snapshot_id) == []


def test_publish_during_quote_read_cannot_turn_the_page_empty(tmp_path):
    engine = create_engine('sqlite:///' + str(tmp_path / 'publication.db'))
    with engine.connect() as connection:
        connection.execute(text('PRAGMA journal_mode=WAL'))
    Base.metadata.create_all(engine)
    now = datetime.now(timezone.utc)
    with Session(engine) as db:
        shop = Shop(token='atomic', name='Atomic', source_url='https://example.com')
        product = Product(slug='atomic', platform='OpenAI', display_name='Atomic')
        snapshot = CatalogSnapshot(source='before', published_at=now)
        db.add_all([shop, product, snapshot])
        db.flush()
        raw = RawProduct(shop_id=shop.id, source_product_key='1', original_name='Atomic quote')
        db.add(raw)
        db.flush()
        db.add(Offer(raw_product_id=raw.id, product_id=product.id, shop_id=shop.id,
                     snapshot_id=snapshot.id, price=Decimal('10'), observed_at=now,
                     stock_status='in_stock', is_comparable=True))
        db.commit()
        old_snapshot_id = snapshot.id
    published = []

    def publish_after_price_read(_conn, _cursor, statement, _parameters, _context, _executemany):
        if published or 'FROM offers' not in statement:
            return
        published.append(None)
        with Session(engine) as writer:
            new = CatalogSnapshot(source='after', published_at=now)
            writer.add(new)
            writer.flush()
            writer.execute(update(Offer).values(snapshot_id=new.id, price=Decimal('20')))
            writer.commit()
            published[0] = new.id

    event.listen(engine, 'after_cursor_execute', publish_after_price_read)
    try:
        with Session(engine) as db:
            page = get_product_offer_page(db, 'atomic', offset=0, limit=1, snapshot_id=old_snapshot_id)
            assert published
            assert len(page) == 1 and page[0].price == Decimal('10')
        with Session(engine) as db:
            page = get_product_offer_page(db, 'atomic', offset=0, limit=1, snapshot_id=published[0])
            assert len(page) == 1 and page[0].price == Decimal('20')
    finally:
        event.remove(engine, 'after_cursor_execute', publish_after_price_read)
        engine.dispose()
