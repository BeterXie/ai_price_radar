from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Optional, Sequence

from .models import ShopScanResult
from .utils import json_loads_or, merge_unique, utc_now


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
                last_error TEXT
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

            CREATE INDEX IF NOT EXISTS idx_candidates_status ON candidates(status);
            CREATE INDEX IF NOT EXISTS idx_matches_token ON matches(token);
            CREATE INDEX IF NOT EXISTS idx_snapshots_token ON product_snapshots(token, observed_at);
            """
        )

        # v1 database migration.
        migrations = {
            "source_score": "INTEGER NOT NULL DEFAULT 0",
            "last_attempt_at": "TEXT",
            "last_success_at": "TEXT",
            "next_retry_at": "TEXT",
            "consecutive_failures": "INTEGER NOT NULL DEFAULT 0",
        }
        for name, ddl in migrations.items():
            self._ensure_column("candidates", name, ddl)
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_candidates_priority ON candidates(source_score DESC, last_attempt_at)")
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
                    token, url, sources, source_score, discovered_at, updated_at, status
                ) VALUES (?, ?, ?, ?, ?, ?, 'pending')
                """,
                (token, url, json.dumps([source], ensure_ascii=False), source_score, now, now),
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
            where = "1=1"
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
            "AND EXISTS (SELECT 1 FROM matches WHERE matches.token = candidates.token)"
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

    def mark_unattempted_pending(self, tokens: Sequence[str]) -> None:
        # Kept for explicitness; candidates remain pending unless save_scan_result is called.
        return

    def save_scan_result(self, result: ShopScanResult, run_id: Optional[int]) -> None:
        now = utc_now()
        with self.conn:
            if result.is_successful_scan:
                # Replace current state only after a successful scan. Historical snapshots remain.
                self.conn.execute("DELETE FROM matches WHERE token=?", (result.token,))
                for product in result.matches:
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
                        json.dumps(product.raw, ensure_ascii=False),
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
                            json.dumps(product.raw, ensure_ascii=False),
                            now,
                        ),
                    )
                self.conn.execute(
                    """
                    UPDATE candidates
                    SET status=?, shop_name=?, shop_url=?, api_host=?,
                        scanned_item_count=?, hit_count=?, scanned_at=?, last_attempt_at=?,
                        last_success_at=?, next_retry_at=NULL, consecutive_failures=0,
                        last_error=NULL, updated_at=?
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
                        result.token,
                    ),
                )
            else:
                # Preserve previously successful current matches on transient failures.
                retry_at = self._retry_at(result.status)
                self.conn.execute(
                    """
                    UPDATE candidates
                    SET status=?, last_attempt_at=?, scanned_at=?, next_retry_at=?,
                        consecutive_failures=consecutive_failures+1,
                        last_error=?, updated_at=?
                    WHERE token=?
                    """,
                    (
                        result.status,
                        now,
                        now,
                        retry_at,
                        result.error[-3000:] if result.error else None,
                        now,
                        result.token,
                    ),
                )

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
