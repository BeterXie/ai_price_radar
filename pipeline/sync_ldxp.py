from __future__ import annotations

import argparse
import os
import json
import sqlite3
from pathlib import Path

from sqlalchemy import func, select

from common import (
    ImportLockUnavailable,
    Offer,
    Shop,
    begin_snapshot,
    ensure_products,
    import_lock,
    session_for,
    upsert_offer,
    utcnow,
)
from intake_bridge import IntakeBridge, IntakeBridgeError


def load_records(path: Path):
    source_uri = f"{path.resolve().as_uri()}?mode=ro"
    conn = sqlite3.connect(source_uri, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        candidate_columns = {row[1] for row in conn.execute("PRAGMA table_info(candidates)")}
        intake_id = "c.intake_id" if "intake_id" in candidate_columns else "NULL AS intake_id"
        intake_attempt_count = (
            "c.intake_attempt_count" if "intake_attempt_count" in candidate_columns else "NULL AS intake_attempt_count"
        )
        rows = conn.execute(
            f"""
            SELECT m.*, c.status AS shop_status, c.source_score, c.last_success_at, c.scanned_at,
                   {intake_id}, {intake_attempt_count}
            FROM matches m
            LEFT JOIN candidates c ON c.token = m.token
            ORDER BY m.collected_at
            """
        )
        for row in rows:
            yield dict(row)
    finally:
        conn.close()


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Import LDXP crawler SQLite into AI Price Radar")
    parser.add_argument("--source-db", required=True, type=Path)
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", ""))
    parser.add_argument("--intake-api-url", default=os.getenv("INTAKE_API_URL", ""))
    parser.add_argument("--intake-worker-key", default=os.getenv("INTAKE_WORKER_KEY", ""))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")
    if not args.source_db.exists():
        parser.error(f"source db not found: {args.source_db}")

    db = session_for(args.database_url)
    created = changed = total = failed = 0
    intake_counts: dict[int, int] = {}
    intake_tokens: dict[int, set[str]] = {}
    intake_attempts: dict[int, int] = {}
    published = False
    published_intake_counts: dict[int, int] = {}
    try:
        with import_lock(db):
            products = ensure_products(db)
            snapshot = begin_snapshot(db, "ldxp")
            for record in load_records(args.source_db):
                total += 1
                try:
                    was_created, was_changed = upsert_offer(db, record, products, snapshot.id)
                    created += int(was_created)
                    changed += int(was_changed)
                    if record.get("intake_id") is not None:
                        intake_id = int(record["intake_id"])
                        intake_counts[intake_id] = intake_counts.get(intake_id, 0) + 1
                        intake_tokens.setdefault(intake_id, set()).add(str(record.get("token") or "").strip())
                        if record.get("intake_attempt_count") is not None:
                            intake_attempts[intake_id] = int(record["intake_attempt_count"])
                    if total % 100 == 0:
                        db.flush()
                except Exception as exc:
                    failed += 1
                    print(json.dumps({"error": str(exc), "record": record.get("product_name")}, ensure_ascii=False))
            if args.dry_run or failed:
                db.rollback()
            else:
                snapshot.offer_count = total
                snapshot.published_at = utcnow()
                db.commit()
                published = True
                published_intake_counts = published_offer_counts(db, snapshot.id, intake_tokens)
    except ImportLockUnavailable as exc:
        db.rollback()
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 3
    finally:
        db.close()
    onboarding_failed = 0
    onboarding_skipped = 0
    if published and intake_counts:
        onboarding_skipped = len(set(intake_counts) - set(published_intake_counts))
        for intake_id in sorted(set(intake_counts) - set(published_intake_counts)):
            print(json.dumps({
                "error": "no public offers in the published snapshot; intake remains validated",
                "intake_id": intake_id,
                "published_data_remains_validated": True,
            }, ensure_ascii=False))
        errors = onboard_published_intakes(
            published_intake_counts,
            intake_attempts,
            api_url=args.intake_api_url,
            worker_key=args.intake_worker_key,
        )
        onboarding_failed = len(errors)
        for error in errors:
            print(json.dumps({**error, "published_data_remains_validated": True}, ensure_ascii=False))
    print(json.dumps({"total": total, "created": created, "changed": changed, "failed": failed, "onboarding_failed": onboarding_failed, "onboarding_skipped": onboarding_skipped, "dry_run": args.dry_run}, ensure_ascii=False))
    return 0 if failed == 0 and onboarding_failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
