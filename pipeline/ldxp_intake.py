from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy import func, select

from common import Offer, Shop
from intake_bridge import IntakeBridge, IntakeBridgeError


def collect_intake_metadata(
    records: Iterable[dict[str, Any]],
) -> tuple[dict[int, set[str]], dict[int, int]]:
    intake_tokens: dict[int, set[str]] = {}
    intake_attempts: dict[int, int] = {}
    for record in records:
        intake_value = record.get("intake_id")
        if intake_value is None:
            continue
        try:
            intake_id = int(intake_value)
        except (TypeError, ValueError):
            continue
        token = str(record.get("token") or "").strip()
        if not token:
            continue
        intake_tokens.setdefault(intake_id, set()).add(token)
        try:
            attempt_count = int(record.get("intake_attempt_count") or 0)
        except (TypeError, ValueError):
            continue
        if attempt_count > 0:
            intake_attempts[intake_id] = attempt_count
    return intake_tokens, intake_attempts


def published_offer_counts(
    db,
    snapshot_id: int,
    intake_tokens: dict[int, set[str]],
) -> dict[int, int]:
    token_to_intake = {
        token.casefold(): intake_id
        for intake_id, tokens in intake_tokens.items()
        for token in tokens
    }
    if not token_to_intake:
        return {}
    rows = db.execute(
        select(Shop.token, Offer.id)
        .join(Offer, Offer.shop_id == Shop.id)
        .where(
            Offer.snapshot_id == snapshot_id,
            Offer.product_id.is_not(None),
            Offer.active.is_(True),
            Offer.approved.is_(True),
            Shop.is_visible.is_(True),
            func.lower(Shop.token).in_(list(token_to_intake)),
        )
    ).all()
    counts: dict[int, int] = {}
    for token, _offer_id in rows:
        intake_id = token_to_intake.get(token.casefold())
        if intake_id is not None:
            counts[intake_id] = counts.get(intake_id, 0) + 1
    return counts


def onboard_published_intakes(
    intake_counts: dict[int, int],
    intake_attempts: dict[int, int],
    *,
    api_url: str,
    worker_key: str,
    bridge_factory=IntakeBridge,
) -> list[dict[str, object]]:
    if not intake_counts:
        return []
    bridge = bridge_factory(api_url, worker_key)
    if not bridge.enabled:
        return [{"error": "intake bridge is not configured", "intake_id": intake_id} for intake_id in intake_counts]
    errors: list[dict[str, object]] = []
    for intake_id, product_count in intake_counts.items():
        attempt_count = intake_attempts.get(intake_id, 0)
        if attempt_count <= 0:
            errors.append({"error": "intake attempt metadata is missing", "intake_id": intake_id})
            continue
        try:
            result = bridge.onboard(
                intake_id=intake_id,
                attempt_count=attempt_count,
                product_count=product_count,
            )
            if result.get("status") != "onboarded":
                errors.append({"error": "intake API did not confirm onboarded", "intake_id": intake_id})
        except IntakeBridgeError as exc:
            errors.append({"error": str(exc), "intake_id": intake_id})
    return errors
