from datetime import datetime, timezone
from decimal import Decimal
import importlib
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models import CommunitySkill, Offer, Product, RawProduct, Shop


def test_seed_initializes_community_skills_when_offers_already_exist(tmp_path: Path, monkeypatch):
    seed_module = importlib.import_module("app.seed")
    engine = create_engine(f"sqlite:///{tmp_path / 'seed.db'}")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)

    with Session(engine) as db:
        product = Product(
            slug="existing-product",
            platform="Test",
            display_name="Existing Product",
            product_type="other",
        )
        shop = Shop(token="existing-shop", name="Existing Shop", source_url="https://example.com")
        db.add_all([product, shop])
        db.flush()
        raw = RawProduct(
            shop_id=shop.id,
            source_product_key="existing-item",
            original_name="Existing Item",
            source_url="https://example.com/item",
            last_seen_at=now,
        )
        db.add(raw)
        db.flush()
        db.add(Offer(
            raw_product_id=raw.id,
            product_id=product.id,
            shop_id=shop.id,
            price=Decimal("1.00"),
            observed_at=now,
        ))
        db.commit()

    monkeypatch.setattr(seed_module, "engine", engine)
    monkeypatch.setattr(seed_module, "SessionLocal", session_factory)
    seed_module.seed()

    with Session(engine) as db:
        assert db.scalar(select(func.count(Offer.id))) >= 1
        assert db.scalar(select(func.count(CommunitySkill.id))) >= 11
