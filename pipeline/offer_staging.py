from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session


class StagedCatalogConflict(RuntimeError):
    """A concurrent catalog decision must survive instead of being overwritten."""


def _relation(db: Session, name: str) -> tuple[str, tuple[str, ...]]:
    relation = db.scalar(text(
        "SELECT format('%I.%I', n.nspname, c.relname) "
        "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE c.oid=to_regclass(:name)"
    ), {"name": name})
    if not relation:
        raise RuntimeError(f"catalog table missing: {name}")
    columns = tuple(db.scalars(text(
        "SELECT attname FROM pg_attribute "
        "WHERE attrelid=CAST(:relation AS regclass) AND attnum>0 AND NOT attisdropped "
        "ORDER BY attnum"
    ), {"relation": relation}))
    return relation, columns


@dataclass(frozen=True, slots=True)
class OfferStaging:
    offers: str
    history: str
    offer_columns: tuple[str, ...]
    history_columns: tuple[str, ...]

    def apply(self, db: Session) -> None:
        """Merge only at the end; never copy the independently changing click count."""
        db.flush()
        db.execute(text("ANALYZE pg_temp.offers"))
        db.execute(text("ANALYZE pg_temp._catalog_offer_baseline"))
        quote = db.get_bind().dialect.identifier_preparer.quote
        columns = ", ".join(quote(column) for column in self.offer_columns)
        selected = ", ".join(f"staged.{quote(column)}" for column in self.offer_columns)
        db.execute(text(
            f"INSERT INTO {self.offers} ({columns}) SELECT {selected} "
            "FROM pg_temp.offers staged LEFT JOIN pg_temp._catalog_offer_baseline baseline "
            "ON baseline.id=staged.id WHERE baseline.id IS NULL"
        ))
        changed = "(to_jsonb(staged) - 'click_count' - 'updated_at') IS DISTINCT FROM baseline.catalog"
        expected = int(db.scalar(text(
            "SELECT count(*) FROM pg_temp.offers staged "
            "JOIN pg_temp._catalog_offer_baseline baseline ON baseline.id=staged.id "
            f"WHERE {changed}"
        )) or 0)
        if expected:
            assignments = ", ".join(
                ("updated_at=GREATEST(live.updated_at,staged.updated_at)" if column == "updated_at"
                 else f"{quote(column)}=staged.{quote(column)}")
                for column in self.offer_columns
                if column not in {"id", "raw_product_id", "shop_id", "created_at", "click_count"}
            )
            result = db.execute(text(
                f"UPDATE {self.offers} live SET {assignments} "
                "FROM pg_temp.offers staged "
                "JOIN pg_temp._catalog_offer_baseline baseline ON baseline.id=staged.id "
                f"WHERE live.id=staged.id AND {changed} "
                "AND (to_jsonb(live) - 'click_count' - 'updated_at') = baseline.catalog"
            ))
            if result.rowcount != expected:
                raise StagedCatalogConflict(
                    "offer catalog changed during local preparation; retry publication"
                )
        history_columns = ", ".join(quote(column) for column in self.history_columns)
        db.execute(text(
            f"INSERT INTO {self.history} ({history_columns}) "
            f"SELECT {history_columns} FROM pg_temp.offer_history"
        ))


def prepare_offer_staging(db: Session) -> OfferStaging | None:
    """Keep row-by-row replay away from public offer rows until the final merge.

    Local temp tables share the transaction and source SAVEPOINTs, require no
    persistent schema changes, and disappear on either commit or rollback.
    """
    if db.get_bind().dialect.name != "postgresql":
        return None
    db.flush()
    offers, offer_columns = _relation(db, "offers")
    history, history_columns = _relation(db, "offer_history")
    path = db.scalar(text("SHOW search_path"))
    db.execute(text(
        f"CREATE TEMP TABLE offers (LIKE {offers} INCLUDING ALL) ON COMMIT DROP"
    ))
    db.execute(text(
        f"CREATE TEMP TABLE offer_history (LIKE {history} INCLUDING ALL) ON COMMIT DROP"
    ))
    db.execute(text(
        "CREATE TEMP TABLE _catalog_offer_baseline "
        "(id bigint PRIMARY KEY, catalog jsonb NOT NULL) ON COMMIT DROP"
    ))
    db.execute(text(
        "WITH staged AS ("
        f"INSERT INTO pg_temp.offers SELECT * FROM {offers} RETURNING *"
        ") INSERT INTO pg_temp._catalog_offer_baseline (id,catalog) "
        "SELECT id,to_jsonb(staged)-'click_count'-'updated_at' FROM staged"
    ))
    db.execute(text("SELECT set_config('search_path', :path, true)"),
               {"path": f"pg_temp, {path}"})
    # A caller may have loaded Offer objects before the temp tables existed.
    db.expire_all()
    return OfferStaging(offers, history, offer_columns, history_columns)
