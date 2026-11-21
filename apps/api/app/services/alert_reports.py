"""Build the latest alert lists from the public catalog sent to readers."""
from __future__ import annotations

import unicodedata
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable, Iterable, TypeVar

T = TypeVar("T")


def title_key(title: str, currency: str = "CNY") -> tuple[str, str]:
    # Keep punctuation, quantities and dates: similar titles need not be the
    # same product. Only normalize typography, casing and repeated whitespace.
    name = " ".join(unicodedata.normalize("NFKC", title).casefold().split())
    currency = currency.strip().upper()
    return name, "CNY" if currency == "RMB" else currency


def lowest_named(items: Iterable[T], *, key: Callable[[T], Any], price: Callable[[T], Any],
                 identity: Callable[[T], int]) -> list[T]:
    chosen: dict[Any, T] = {}
    for item in items:
        group = key(item)
        previous = chosen.get(group)
        if previous is None or (Decimal(str(price(item))), identity(item)) < (Decimal(str(price(previous))), identity(previous)):
            chosen[group] = item
    return list(chosen.values())


def unique_price_events(events: Iterable[T]) -> list[T]:
    return lowest_named(events, key=lambda e: title_key(e.product_name, e.currency),
                        price=lambda e: e.new_price, identity=lambda e: e.offer_id)


def unique_team_offers(offers: Iterable[T]) -> list[T]:
    return sorted(lowest_named(offers, key=lambda o: (title_key(o.product_name), o.ends_at),
                              price=lambda o: o.price, identity=lambda o: o.offer_id),
                  key=lambda o: (o.price, o.offer_id))


def _time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def public_offer_prices(snapshot: dict) -> dict[int, tuple[Decimal, str]]:
    return {offer["id"]: (Decimal(str(offer["price"])), title_key("", offer["currency"])[1])
            for product in snapshot["products"] for offer in product["offers"] if offer["price"] is not None}


def build_alert_report(snapshot: dict, events: list[Any], *, previous_prices: dict | None = None) -> dict:
    from .team_rules import (
        TEAM_HEAD_PRICE_LIMIT, TEAM_PRICE_LIMIT, is_head_car_title,
        is_team_account_title, team_title_ends_at,
    )

    published_at = _time(snapshot["published_at"])
    available = {}
    team = []
    for product in snapshot["products"]:
        for offer in product["offers"]:
            if (offer["price"] is None or Decimal(str(offer["price"])) <= 0
                    or offer["stock_status"] != "in_stock"
                    or (offer.get("stock_count") is not None and offer["stock_count"] <= 0)):
                continue
            price = Decimal(str(offer["price"]))
            row = {
                "offer_id": offer["id"], "product_name": offer["original_name"],
                "product_slug": product["slug"], "shop_name": offer["shop_name"],
                "price": f"{price:.2f}", "currency": title_key("", offer["currency"])[1],
                "observed_at": offer["observed_at"],
                "source_url": offer.get("source_url", ""),
            }
            available[offer["id"]] = row
            if (product["slug"] not in ("chatgpt-business", "chatgpt-access-service")
                    or row["currency"] != "CNY" or not is_team_account_title(row["product_name"])):
                continue
            head = is_head_car_title(row["product_name"])
            if price > (TEAM_HEAD_PRICE_LIMIT if head else TEAM_PRICE_LIMIT):
                continue
            ends = team_title_ends_at(row["product_name"], observed_at=_time(offer["observed_at"]))
            if ends is not None and ends > published_at:
                team.append({**row, "ends_at": ends.isoformat(), "is_head_car": head})

    changes = []
    for offer_id in dict.fromkeys(event.offer_id for event in events):
        row = available.get(offer_id)
        baseline = (previous_prices or {}).get(offer_id)
        # Never publish private/hidden/stale rows or a transition inconsistent
        # with the frozen public price. No price is reconstructed from today's DB.
        if row is None or baseline is None or baseline[1] != row["currency"] or baseline[0] < 0:
            continue
        old_price = baseline[0]
        diff = Decimal(row["price"]) - old_price
        if not diff:
            continue
        changes.append({**row, "old_price": f"{old_price:.2f}", "diff": f"{diff:.2f}",
                        "percent_change": round(float(diff / old_price * 100), 2) if old_price else 0.0,
                        "is_drop": diff < 0})
    changes = lowest_named(changes, key=lambda r: title_key(r["product_name"], r["currency"]),
                           price=lambda r: r["price"], identity=lambda r: r["offer_id"])
    team = lowest_named(team, key=lambda r: (title_key(r["product_name"]), r["ends_at"]),
                        price=lambda r: r["price"], identity=lambda r: r["offer_id"])
    order_change = lambda r: (-abs(r["percent_change"]), r["currency"], Decimal(r["price"]), r["offer_id"])
    return {
        "schema_version": "price-radar.alerts.v1", "snapshot_id": int(snapshot["snapshot_id"]),
        "published_at": snapshot["published_at"], "stale_offer_hours": snapshot["stale_offer_hours"],
        "drops": sorted((r for r in changes if r["is_drop"]), key=order_change),
        "rises": sorted((r for r in changes if not r["is_drop"]), key=order_change),
        "team": sorted(team, key=lambda r: (Decimal(r["price"]), r["ends_at"], r["offer_id"])),
    }
