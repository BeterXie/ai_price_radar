from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Optional, Sequence

from .models import ProductMatch, ShopScanResult
from .utils import json_loads_or, merge_unique, utc_now


POLICY_STATUSES = frozenset({
    "active", "paused", "blocked", "challenge", "opted_out", "legal_hold", "unsupported",
})


class StateDB:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=5000")
        self._init_schema()

    def close(self) -> None:
        self.conn.close()

    def _columns(self, table: str) -> set[str]:
        return {row[1] for row in self.conn.execute(f"PRAGMA table_info({table})")}

    def _ensure_column(self, table: str, name: str, ddl: str) -> None:
        if name not in self._columns(table):
            self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")

    def _init_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS candidates (
                token TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                sources TEXT NOT NULL DEFAULT '[]',
                source_score INTEGER NOT NULL DEFAULT 0,
                discovered_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                shop_name TEXT,
                shop_url TEXT,
                api_host TEXT,
                scanned_item_count INTEGER NOT NULL DEFAULT 0,
                hit_count INTEGER NOT NULL DEFAULT 0,
                scanned_at TEXT,
                last_attempt_at TEXT,
                last_success_at TEXT,
                next_retry_at TEXT,
                consecutive_failures INTEGER NOT NULL DEFAULT 0,
                last_error TEXT,
                intake_id INTEGER,
                intake_attempt_count INTEGER
            );

            CREATE TABLE IF NOT EXISTS matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token TEXT NOT NULL,
                shop_name TEXT,
                shop_url TEXT,
                api_host TEXT,
                product_key TEXT,
                product_name TEXT NOT NULL,
                matched_keywords TEXT NOT NULL,
                listed_price REAL,
                real_price REAL,
                stock_count INTEGER,
                product_status TEXT,
                category_name TEXT,
                product_url TEXT,
                auto_delivery TEXT,
                goods_type TEXT,
                raw_json TEXT,
                collected_at TEXT NOT NULL,
                UNIQUE(token, product_key, product_name)
            );

            CREATE TABLE IF NOT EXISTS scan_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                command TEXT NOT NULL,
                keywords TEXT NOT NULL,
                engine TEXT NOT NULL,
                config_json TEXT NOT NULL,
                attempted INTEGER NOT NULL DEFAULT 0,
                successful INTEGER NOT NULL DEFAULT 0,
                failed INTEGER NOT NULL DEFAULT 0,
                blocked INTEGER NOT NULL DEFAULT 0,
                matches INTEGER NOT NULL DEFAULT 0,
                circuit_broken INTEGER NOT NULL DEFAULT 0,
                note TEXT
            );

            CREATE TABLE IF NOT EXISTS product_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER,
                token TEXT NOT NULL,
                product_key TEXT,
                product_name TEXT NOT NULL,
                matched_keywords TEXT NOT NULL,
                listed_price REAL,
                real_price REAL,
                stock_count INTEGER,
                product_status TEXT,
                category_name TEXT,
                product_url TEXT,
                raw_json TEXT,
                observed_at TEXT NOT NULL,
                FOREIGN KEY(run_id) REFERENCES scan_runs(id)
            );

            CREATE TABLE IF NOT EXISTS dujiao_candidates (
                origin TEXT PRIMARY KEY,
                discovered_urls TEXT NOT NULL DEFAULT '[]',
                sources TEXT NOT NULL DEFAULT '[]',
                fingerprints TEXT NOT NULL DEFAULT '[]',
                api_verified INTEGER NOT NULL DEFAULT 0,
                product_count INTEGER,
                matched_product_count INTEGER NOT NULL DEFAULT 0,
                matched_products TEXT NOT NULL DEFAULT '[]',
                status TEXT NOT NULL DEFAULT 'validation_failed',
                review_status TEXT NOT NULL DEFAULT 'pending_review',
                review_note TEXT,
                reviewed_at TEXT,
                first_seen_at TEXT NOT NULL,
                last_verified_at TEXT NOT NULL,
                last_error TEXT,
                site_name TEXT,
                re_review_reason TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_candidates_status ON candidates(status);
            CREATE INDEX IF NOT EXISTS idx_matches_token ON matches(token);
            CREATE INDEX IF NOT EXISTS idx_snapshots_token ON product_snapshots(token, observed_at);
            CREATE INDEX IF NOT EXISTS idx_dujiao_candidates_status ON dujiao_candidates(status, last_verified_at);
            """
        )

        # v1 database migration.
        migrations = {
            "source_score": "INTEGER NOT NULL DEFAULT 0",
            "last_attempt_at": "TEXT",
            "last_success_at": "TEXT",
            "next_retry_at": "TEXT",
            "consecutive_failures": "INTEGER NOT NULL DEFAULT 0",
            "intake_id": "INTEGER",
            "intake_attempt_count": "INTEGER",
            "next_scan_at": "TEXT",
            "scan_interval_minutes": "INTEGER NOT NULL DEFAULT 720",
            "unchanged_streak": "INTEGER NOT NULL DEFAULT 0",
            "last_changed_at": "TEXT",
            "last_content_hash": "TEXT NOT NULL DEFAULT ''",
            "blocked_until": "TEXT",
            "policy_status": "TEXT NOT NULL DEFAULT 'active'",
            "policy_reason": "TEXT NOT NULL DEFAULT ''",
            "opt_out_at": "TEXT",
            "last_http_status": "INTEGER",
            "daily_request_count": "INTEGER NOT NULL DEFAULT 0",
            "daily_request_date": "TEXT",
            "daily_scan_count": "INTEGER NOT NULL DEFAULT 0",
            "daily_scan_date": "TEXT",
        }
        for name, ddl in migrations.items():
            self._ensure_column("candidates", name, ddl)
        dujiao_migrations = {
            "site_name": "TEXT",
            "re_review_reason": "TEXT",
        }
        for name, ddl in dujiao_migrations.items():
            self._ensure_column("dujiao_candidates", name, ddl)
        self.conn.execute(
            """
            UPDATE dujiao_candidates SET review_status='pending_review'
            WHERE review_status NOT IN (
                'pending_review', 'approved', 'rejected', 'needs_re_review', 'disabled'
            )
            """
        )
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_candidates_priority ON candidates(source_score DESC, last_attempt_at)")
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_candidates_due ON candidates(policy_status, next_scan_at)"
        )
        self.conn.commit()

    def start_run(self, command: str, keywords: Sequence[str], engine: str, config: dict[str, Any]) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO scan_runs(started_at, command, keywords, engine, config_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                utc_now(),
                command,
                json.dumps(list(keywords), ensure_ascii=False),
                engine,
                json.dumps(config, ensure_ascii=False, default=str),
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def finish_run(
        self,
        run_id: int,
        *,
        attempted: int,
        successful: int,
        failed: int,
        blocked: int,
        matches: int,
        circuit_broken: bool,
        note: str = "",
    ) -> None:
        self.conn.execute(
            """
            UPDATE scan_runs
            SET finished_at=?, attempted=?, successful=?, failed=?, blocked=?, matches=?,
                circuit_broken=?, note=?
            WHERE id=?
            """,
            (
                utc_now(), attempted, successful, failed, blocked, matches,
                int(circuit_broken), note, run_id,
            ),
        )
        self.conn.commit()

    def latest_run(self) -> Optional[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM scan_runs ORDER BY id DESC LIMIT 1").fetchone()

    def upsert_candidate(self, token: str, url: str, source: str, source_score: int) -> bool:
        now = utc_now()
        row = self.conn.execute("SELECT sources, source_score FROM candidates WHERE token=?", (token,)).fetchone()
        if row:
            sources = merge_unique([*json_loads_or(row["sources"], []), source])
            self.conn.execute(
                """
                UPDATE candidates
                SET url=?, sources=?, source_score=MAX(source_score, ?), updated_at=?
                WHERE token=?
                """,
                (url, json.dumps(sources, ensure_ascii=False), source_score, now, token),
            )
            inserted = False
        else:
            self.conn.execute(
                """
                INSERT INTO candidates(
                    token, url, sources, source_score, discovered_at, updated_at, status,
                    next_scan_at, scan_interval_minutes
                ) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, 720)
                """,
                (token, url, json.dumps([source], ensure_ascii=False), source_score, now, now, now),
            )
            inserted = True
        self.conn.commit()
        return inserted

    @staticmethod
    def _dujiao_re_review_reason(row: sqlite3.Row, result: Any) -> str:
        if result.status != "pending_review":
            detail = str(result.error or "").strip()
            return f"verification changed to {result.status}" + (f": {detail}" if detail else "")
        old_name = " ".join(str(row["site_name"] or "").casefold().split())
        new_name = " ".join(str(result.site_name or "").casefold().split())
        if old_name and new_name and old_name not in new_name and new_name not in old_name:
            return f"site identity changed from {row['site_name']!r} to {result.site_name!r}"
        return ""

    def get_dujiao_candidate(self, origin: str) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM dujiao_candidates WHERE origin=?",
            (origin,),
        ).fetchone()

    def record_dujiao_discovery(self, origin: str, discovered_url: str, source: str) -> bool:
        row = self.get_dujiao_candidate(origin)
        if row is None:
            return False
        discovered_urls = merge_unique([*json_loads_or(row["discovered_urls"], []), discovered_url])
        sources = merge_unique([*json_loads_or(row["sources"], []), source])
        self.conn.execute(
            "UPDATE dujiao_candidates SET discovered_urls=?, sources=? WHERE origin=?",
            (
                json.dumps(discovered_urls, ensure_ascii=False),
                json.dumps(sources, ensure_ascii=False),
                origin,
            ),
        )
        self.conn.commit()
        return True

    def upsert_dujiao_candidate(self, result: Any) -> bool:
        row = self.conn.execute(
            """
            SELECT discovered_urls, sources, review_status, first_seen_at,
                   site_name, re_review_reason
            FROM dujiao_candidates WHERE origin=?
            """,
            (result.origin,),
        ).fetchone()
        discovered_urls = merge_unique([
            *(json_loads_or(row["discovered_urls"], []) if row else []),
            result.discovered_url,
        ])
        sources = merge_unique([
            *(json_loads_or(row["sources"], []) if row else []),
            result.discovered_by,
        ])
        first_seen_at = row["first_seen_at"] if row else result.last_verified_at
        review_status = "approved" if result.status == "pending_review" else "pending_review"
        re_review_reason = ""
        if row:
            previous_review = row["review_status"]
            if previous_review == "approved":
                re_review_reason = self._dujiao_re_review_reason(row, result)
                review_status = "needs_re_review" if re_review_reason else "approved"
            elif previous_review == "needs_re_review":
                review_status = previous_review
                re_review_reason = self._dujiao_re_review_reason(row, result) or str(row["re_review_reason"] or "")
            elif previous_review in {"rejected", "disabled"}:
                review_status = previous_review
        self.conn.execute(
            """
            INSERT INTO dujiao_candidates(
                origin, discovered_urls, sources, fingerprints, api_verified,
                product_count, matched_product_count, matched_products, status,
                review_status, first_seen_at, last_verified_at, last_error,
                site_name, re_review_reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(origin) DO UPDATE SET
                discovered_urls=excluded.discovered_urls,
                sources=excluded.sources,
                fingerprints=excluded.fingerprints,
                api_verified=excluded.api_verified,
                product_count=excluded.product_count,
                matched_product_count=excluded.matched_product_count,
                matched_products=excluded.matched_products,
                status=excluded.status,
                review_status=excluded.review_status,
                last_verified_at=excluded.last_verified_at,
                last_error=excluded.last_error,
                site_name=excluded.site_name,
                re_review_reason=excluded.re_review_reason
            """,
            (
                result.origin,
                json.dumps(discovered_urls, ensure_ascii=False),
                json.dumps(sources, ensure_ascii=False),
                json.dumps(result.fingerprints, ensure_ascii=False),
                int(result.api_verified),
                result.product_count,
                len(result.matched_products),
                json.dumps(result.matched_products, ensure_ascii=False),
                result.status,
                review_status,
                first_seen_at,
                result.last_verified_at,
                result.error[-500:] if result.error else None,
                result.site_name or None,
                re_review_reason[:500] or None,
            ),
        )
        self.conn.commit()
        return row is None

    def dujiao_candidate_count(self) -> int:
        return int(self.conn.execute("SELECT COUNT(*) FROM dujiao_candidates").fetchone()[0])

    def list_stale_dujiao_candidates(self, stale_before: str, *, limit: int | None = None) -> list[sqlite3.Row]:
        sql = """
            SELECT * FROM dujiao_candidates
            WHERE last_verified_at <= ? AND review_status <> 'disabled'
            ORDER BY CASE review_status
                WHEN 'approved' THEN 0
                WHEN 'needs_re_review' THEN 1
                ELSE 2
            END, last_verified_at, origin
        """
        params: list[Any] = [stale_before]
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        return list(self.conn.execute(sql, params).fetchall())

    def review_dujiao_candidate(self, origin: str, decision: str, note: str = "") -> bool:
        if decision not in {"approved", "rejected", "disabled"}:
            raise ValueError("invalid Dujiao review decision")
        row = self.conn.execute(
            "SELECT status FROM dujiao_candidates WHERE origin=?",
            (origin,),
        ).fetchone()
        if row is None:
            return False
        if decision == "approved" and row["status"] != "pending_review":
            raise ValueError("Dujiao candidate is not eligible for review")
        self.conn.execute(
            """
            UPDATE dujiao_candidates
            SET review_status=?, review_note=?, reviewed_at=?, re_review_reason=NULL
            WHERE origin=?
            """,
            (decision, note.strip()[:1000] or None, utc_now(), origin),
        )
        self.conn.commit()
        return True

    def list_dujiao_candidates(
        self,
        *,
        review_status: str | None = None,
        verification_status: str | None = None,
    ) -> list[sqlite3.Row]:
        conditions: list[str] = []
        params: list[str] = []
        if review_status:
            conditions.append("review_status=?")
            params.append(review_status)
        if verification_status:
            conditions.append("status=?")
            params.append(verification_status)
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        return list(self.conn.execute(
            f"""
            SELECT * FROM dujiao_candidates{where}
            ORDER BY CASE WHEN review_status='pending_review' THEN 0 ELSE 1 END,
                     matched_product_count DESC, last_verified_at DESC, origin
            """,
            params,
        ).fetchall())

    def upsert_intake_candidate(
        self,
        *,
        intake_id: int,
        token: str,
        url: str,
        shop_name: str,
        attempt_count: int,
    ) -> bool:
        now = utc_now()
        row = self.conn.execute(
            "SELECT sources FROM candidates WHERE token=?", (token,)
        ).fetchone()
        source_score = 1_000_000
        if row:
            sources = merge_unique([*json_loads_or(row["sources"], []), "intake"])
            self.conn.execute(
                """
                UPDATE candidates
                SET url=?, sources=?, source_score=MAX(source_score, ?), updated_at=?,
                    status='pending', next_retry_at=NULL, intake_id=?, intake_attempt_count=?,
                    shop_name=COALESCE(NULLIF(?, ''), shop_name), shop_url=?
                WHERE token=?
                """,
                (
                    url,
                    json.dumps(sources, ensure_ascii=False),
                    source_score,
                    now,
                    intake_id,
                    attempt_count,
                    shop_name,
                    url,
                    token,
                ),
            )
            inserted = False
        else:
            self.conn.execute(
                """
                INSERT INTO candidates(
                    token, url, sources, source_score, discovered_at, updated_at, status,
                    shop_name, shop_url, intake_id, intake_attempt_count,
                    next_scan_at, scan_interval_minutes
                ) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, 720)
                """,
                (
                    token,
                    url,
                    json.dumps(["intake"], ensure_ascii=False),
                    source_score,
                    now,
                    now,
                    shop_name,
                    url,
                    intake_id,
                    attempt_count,
                    now,
                ),
            )
            inserted = True
        self.conn.commit()
        return inserted

    def candidate_count(self) -> int:
        return int(self.conn.execute("SELECT COUNT(*) FROM candidates").fetchone()[0])

    def list_candidates(
        self,
        *,
        rescan: bool = False,
        retry_blocked: bool = False,
        retry_failed: bool = True,
        matched_only: bool = False,
        limit: Optional[int] = None,
    ) -> list[sqlite3.Row]:
        if rescan:
            where = "1=1" if retry_blocked else "status NOT IN ('blocked', 'challenge_required')"
        else:
            allowed = ["pending"]
            if retry_failed:
                allowed.extend(["network_error", "parse_error", "api_changed", "failed", "rate_limited"])
            if retry_blocked:
                allowed.extend(["blocked", "challenge_required"])
            marks = ",".join("?" for _ in allowed)
            where = f"status IN ({marks})"
        params: list[Any] = [] if rescan else allowed
        matched_clause = (
            "AND (candidates.intake_id IS NOT NULL OR EXISTS "
            "(SELECT 1 FROM matches WHERE matches.token = candidates.token))"
            if matched_only
            else ""
        )
        sql = f"""
            SELECT * FROM candidates
            WHERE {where}
              AND (next_retry_at IS NULL OR next_retry_at <= ?)
              {matched_clause}
            ORDER BY source_score DESC,
                     CASE WHEN last_attempt_at IS NULL THEN 0 ELSE 1 END,
                     last_attempt_at ASC,
                     discovered_at DESC
        """
        params.append(utc_now())
        if limit is not None and limit > 0:
            sql += " LIMIT ?"
            params.append(limit)
        return list(self.conn.execute(sql, params).fetchall())

    def list_due_candidates(self, *, limit: int = 20, now: str | None = None) -> list[sqlite3.Row]:
        now = now or utc_now()
        rows = self.conn.execute(
            """
            SELECT * FROM candidates
            WHERE policy_status IN ('active', 'paused', 'blocked', 'challenge')
              AND next_scan_at IS NOT NULL AND next_scan_at <= ?
              AND (blocked_until IS NULL OR blocked_until <= ?)
            ORDER BY next_scan_at, token
            LIMIT ?
            """,
            (now, now, limit),
        ).fetchall()
        return [dict(row) for row in rows]

    def claim_due_candidate(self, token: str, *, now: str | None = None) -> bool:
        """Atomically reserve and wake a due shop.

        Paused/blocked/challenge shops whose backoff window has expired are
        restored to ``active`` as part of the claim, so the scanner can actually
        run after 403/429/challenge backoff.
        """
        now = now or utc_now()
        cursor = self.conn.execute(
            """
            UPDATE candidates
            SET next_scan_at = ?, policy_status = 'active', blocked_until = NULL
            WHERE token = ?
              AND policy_status IN ('active', 'paused', 'blocked', 'challenge')
              AND next_scan_at IS NOT NULL AND next_scan_at <= ?
              AND (blocked_until IS NULL OR blocked_until <= ?)
            """,
            (
                (self._add_minutes(now, 10)),
                token,
                now,
                now,
            ),
        )
        self.conn.commit()
        return cursor.rowcount > 0

    @staticmethod
    def _add_minutes(value: str, minutes: int) -> str:
        from datetime import datetime, timedelta, timezone

        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return (parsed + timedelta(minutes=minutes)).replace(microsecond=0).isoformat()

    def set_policy_status(self, token: str, status: str, reason: str = "") -> bool:
        if status not in POLICY_STATUSES:
            raise ValueError(f"invalid policy status: {status}")
        cursor = self.conn.execute(
            "UPDATE candidates SET policy_status=?, policy_reason=?, opt_out_at=? WHERE token=?",
            (status, reason[:1000], utc_now() if status == "opted_out" else None, token),
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def record_daily_request(self, token: str, *, count: int = 1, now: str | None = None) -> None:
        now = now or utc_now()
        count = max(0, int(count))
        if count == 0:
            return
        day = now[:10]
        self.conn.execute(
            """
            UPDATE candidates
            SET daily_request_count = CASE WHEN daily_request_date = ? THEN daily_request_count + ? ELSE ? END,
                daily_request_date = ?
            WHERE token = ?
            """,
            (day, count, count, day, token),
        )
        self.conn.commit()

    def record_daily_scan(self, token: str, *, now: str | None = None) -> None:
        now = now or utc_now()
        day = now[:10]
        self.conn.execute(
            """
            UPDATE candidates
            SET daily_scan_count = CASE WHEN daily_scan_date = ? THEN daily_scan_count + 1 ELSE 1 END,
                daily_scan_date = ?
            WHERE token = ?
            """,
            (day, day, token),
        )
        self.conn.commit()

    def mark_unattempted_pending(self, tokens: Sequence[str]) -> None:
        # Kept for explicitness; candidates remain pending unless save_scan_result is called.
        return

    def save_scan_result(self, result: ShopScanResult, run_id: Optional[int]) -> None:
        now = utc_now()
        row = self.conn.execute(
            "SELECT unchanged_streak, scan_interval_minutes, last_content_hash FROM candidates WHERE token=?",
            (result.token,),
        ).fetchone()
        base_streak = int(row["unchanged_streak"]) if row else 0
        previous_hash = str(row["last_content_hash"] or "") if row else ""
        (
            next_scan_at,
            interval_minutes,
            unchanged_streak,
            last_changed_at,
            content_hash,
        ) = self._schedule_after(result, base_streak=base_streak, previous_hash=previous_hash)
        with self.conn:
            if result.is_successful_scan:
                # Replace current state only after a successful scan. Historical snapshots remain.
                self.conn.execute("DELETE FROM matches WHERE token=?", (result.token,))
                for product in result.matches:
                    audit_summary = json.dumps(
                        {
                            "source": "public_dom",
                            "selector_version": "ldxp-dom-v1",
                            "field_presence": [
                                field
                                for field in ("product_name", "listed_price", "stock_count", "product_status", "product_url")
                                if getattr(product, field, None) not in (None, "", 0)
                            ],
                            "content_hash": product.content_hash,
                            "redacted_field_count": product.redacted_field_count,
                        },
                        ensure_ascii=False,
                    )
                    payload = (
                        result.token,
                        result.shop_name,
                        result.shop_url,
                        result.api_host,
                        product.product_key,
                        product.product_name,
                        json.dumps(product.matched_keywords, ensure_ascii=False),
                        product.listed_price,
                        product.real_price,
                        product.stock_count,
                        product.product_status,
                        product.category_name,
                        product.product_url,
                        product.auto_delivery,
                        product.goods_type,
                        audit_summary,
                        now,
                    )
                    self.conn.execute(
                        """
                        INSERT OR REPLACE INTO matches(
                            token, shop_name, shop_url, api_host, product_key, product_name,
                            matched_keywords, listed_price, real_price, stock_count,
                            product_status, category_name, product_url, auto_delivery,
                            goods_type, raw_json, collected_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        payload,
                    )
                    self.conn.execute(
                        """
                        INSERT INTO product_snapshots(
                            run_id, token, product_key, product_name, matched_keywords,
                            listed_price, real_price, stock_count, product_status,
                            category_name, product_url, raw_json, observed_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            run_id,
                            result.token,
                            product.product_key,
                            product.product_name,
                            json.dumps(product.matched_keywords, ensure_ascii=False),
                            product.listed_price,
                            product.real_price,
                            product.stock_count,
                            product.product_status,
                            product.category_name,
                            product.product_url,
                            audit_summary,
                            now,
                        ),
                    )
                self.conn.execute(
                    """
                    UPDATE candidates
                    SET status=?, shop_name=?, shop_url=?, api_host=?,
                        scanned_item_count=?, hit_count=?, scanned_at=?, last_attempt_at=?,
                        last_success_at=?, next_retry_at=NULL, consecutive_failures=0,
                        last_error=NULL, updated_at=?, last_http_status=?,
                        next_scan_at=?, scan_interval_minutes=?, unchanged_streak=?,
                        last_changed_at=?, last_content_hash=?,
                        blocked_until=NULL, policy_status='active', policy_reason=''
                    WHERE token=?
                    """,
                    (
                        result.status,
                        result.shop_name,
                        result.shop_url,
                        result.api_host,
                        result.scanned_item_count,
                        len(result.matches),
                        now,
                        now,
                        now,
                        now,
                        result.http_status,
                        next_scan_at,
                        interval_minutes,
                        unchanged_streak,
                        last_changed_at,
                        content_hash,
                        result.token,
                    ),
                )
            else:
                # Preserve previously successful current matches on transient failures.
                retry_at = self._retry_at(result.status)
                blocked_until = self._blocked_until(result.status)
                policy_status = self._policy_status_after(result.status)
                self.conn.execute(
                    """
                    UPDATE candidates
                    SET status=?, last_attempt_at=?, scanned_at=?, next_retry_at=?,
                        consecutive_failures=consecutive_failures+1,
                        last_error=?, updated_at=?, last_http_status=?,
                        blocked_until=COALESCE(?, blocked_until),
                        policy_status=COALESCE(?, policy_status),
                        next_scan_at=?, scan_interval_minutes=?
                    WHERE token=?
                    """,
                    (
                        result.status,
                        now,
                        now,
                        retry_at,
                        result.error[-3000:] if result.error else None,
                        now,
                        result.http_status,
                        blocked_until,
                        policy_status,
                        next_scan_at,
                        interval_minutes,
                        result.token,
                    ),
                )

    @staticmethod
    def _schedule_after(
        result: ShopScanResult,
        *,
        base_streak: int,
        previous_hash: str,
    ) -> tuple[str, int, int, Optional[str], str]:
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        unchanged_streak = base_streak
        interval = 720
        last_changed_at: Optional[str] = None
        content_hash = ""
        if result.status in {"success", "partial_success"} and result.matches:
            content_hash = "|".join(sorted({product.content_hash for product in result.matches}))
            if content_hash and content_hash == previous_hash:
                unchanged_streak = base_streak + 1
                interval = 120 if unchanged_streak <= 3 else 360 if unchanged_streak <= 10 else 720
            else:
                unchanged_streak = 0
                interval = 60
                last_changed_at = now.replace(microsecond=0).isoformat()
        elif result.status in {"success", "partial_success", "no_match"}:
            unchanged_streak = base_streak + 1
            interval = 120 if unchanged_streak <= 3 else 360 if unchanged_streak <= 10 else 720
        elif result.status == "empty_shop":
            interval = 720
        elif result.status == "closed":
            interval = 1440
        elif result.status == "rate_limited":
            interval = 1440
        elif result.status == "blocked":
            interval = 10080
        elif result.status == "challenge_required":
            interval = 43200
        elif result.status in {"unsupported", "policy_blocked"}:
            interval = 43200
        next_scan_at = (now + timedelta(minutes=interval)).replace(microsecond=0).isoformat()
        return next_scan_at, interval, unchanged_streak, last_changed_at, content_hash

    @staticmethod
    def _retry_at(status: str) -> Optional[str]:
        # ISO UTC text remains lexically sortable. Keep blocked/challenge manual-only.
        from datetime import datetime, timedelta, timezone

        delay = {
            "network_error": timedelta(minutes=10),
            "rate_limited": timedelta(hours=1),
            "parse_error": timedelta(hours=6),
            "api_changed": timedelta(hours=12),
            "failed": timedelta(minutes=30),
        }.get(status)
        if delay is None:
            return None
        return (datetime.now(timezone.utc) + delay).replace(microsecond=0).isoformat()

    @staticmethod
    def _blocked_until(status: str) -> Optional[str]:
        from datetime import datetime, timedelta, timezone

        delays = {
            "rate_limited": timedelta(hours=24),
            "blocked": timedelta(days=7),
            "challenge_required": timedelta(days=30),
        }
        delay = delays.get(status)
        if delay is None:
            return None
        return (datetime.now(timezone.utc) + delay).replace(microsecond=0).isoformat()

    @staticmethod
    def _policy_status_after(status: str) -> Optional[str]:
        if status == "unsupported":
            return "unsupported"
        if status == "challenge_required":
            return "challenge"
        if status == "blocked":
            return "blocked"
        if status == "rate_limited":
            return "paused"
        return None

    def rows_for_export(self) -> tuple[list[sqlite3.Row], list[sqlite3.Row], list[sqlite3.Row]]:
        candidates = list(
            self.conn.execute(
                """
                SELECT * FROM candidates
                ORDER BY hit_count DESC, source_score DESC, shop_name COLLATE NOCASE, token
                """
            ).fetchall()
        )
        matches = list(
            self.conn.execute(
                """
                SELECT * FROM matches
                ORDER BY shop_name COLLATE NOCASE, listed_price, product_name COLLATE NOCASE
                """
            ).fetchall()
        )
        runs = list(self.conn.execute("SELECT * FROM scan_runs ORDER BY id DESC LIMIT 100").fetchall())
        return candidates, matches, runs

    def status_counts(self) -> dict[str, int]:
        return {
            row["status"]: int(row["n"])
            for row in self.conn.execute(
                "SELECT status, COUNT(*) AS n FROM candidates GROUP BY status"
            )
        }
