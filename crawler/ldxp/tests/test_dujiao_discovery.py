from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from ldxp_crawler.db import StateDB
from ldxp_crawler.dujiao_discovery import (
    MAX_RESPONSE_BYTES,
    DujiaoDiscovery,
    DujiaoVerificationResult,
    DujiaoVerifier,
    bing_queries,
    extract_bing_result_urls,
    is_excluded_origin,
    normalize_candidate_origin,
)
from ldxp_gpt_crawler import build_parser


class FakeResponse:
    def __init__(
        self,
        status_code: int,
        *,
        text: str = "",
        document=None,
        headers=None,
        chunks: list[bytes] | None = None,
    ):
        self.status_code = status_code
        self.headers = headers or {}
        self.encoding = "utf-8"
        body = json.dumps(document, ensure_ascii=False).encode("utf-8") if document is not None else text.encode("utf-8")
        self.chunks = chunks if chunks is not None else [body]
        self.closed = False
        self.iterated_chunks = 0

    def iter_content(self, chunk_size: int):
        assert chunk_size == 64 * 1024
        for chunk in self.chunks:
            self.iterated_chunks += 1
            yield chunk

    def close(self):
        self.closed = True


class FakeSession:
    def __init__(self, handler):
        self.handler = handler
        self.calls: list[tuple[str, dict]] = []

    def get(self, url: str, **kwargs):
        self.calls.append((url, kwargs))
        return self.handler(url, kwargs)


def _products(items, *, page=1, total=None, total_page=1):
    return {
        "status_code": 0,
        "msg": "success",
        "data": items,
        "pagination": {
            "page": page,
            "page_size": 100,
            "total": len(items) if total is None else total,
            "total_page": total_page,
        },
    }


def test_candidate_urls_reduce_to_https_origin_and_exclude_official_sites():
    assert normalize_candidate_origin("shop.example.com/buy/20") == "https://shop.example.com"
    assert normalize_candidate_origin("https://Shop.Example.com/products/chatgpt-plus?ref=search") == "https://shop.example.com"
    assert normalize_candidate_origin("http://shop.example.com/") == "https://shop.example.com"
    assert normalize_candidate_origin("javascript:alert(1)") is None
    assert normalize_candidate_origin("https://user:pass@shop.example.com") is None
    assert is_excluded_origin("https://demo.dujiao-next.com") is True
    assert is_excluded_origin("https://dujiao-next.com") is True
    assert is_excluded_origin("https://shop.example.com") is False


def test_cli_exposes_bounded_dujiao_discovery_command():
    args = build_parser().parse_args(["discover-dujiao", "--sources", "seed", "--seed", "https://shop.example.com"])
    assert args.command == "discover-dujiao"
    assert args.sources == "seed"
    assert args.request_interval == 2.0
    assert args.max_api_pages == 5
    assert args.max_new_candidates == 500
    assert args.max_processed_candidates == 2000
    assert args.reverify_stale_hours == 24.0
    review = build_parser().parse_args([
        "review-dujiao",
        "--origin", "https://shop.example.com",
        "--decision", "approve",
    ])
    assert review.command == "review-dujiao"
    assert review.decision == "approve"


def test_verifier_uses_home_fingerprint_as_supporting_evidence(monkeypatch):
    def handler(url: str, _kwargs: dict):
        parsed = urlsplit(url)
        if parsed.path == "/":
            return FakeResponse(200, text="<footer>Dujiao-Next</footer><h2>Featured Products</h2>")
        if parsed.path == "/api/v1/public/products":
            page = int(parse_qs(parsed.query)["page"][0])
            if page == 1:
                return FakeResponse(200, document=_products(
                    [{"slug": "vpn", "title": {"zh-CN": "VPN 月卡"}}],
                    page=1,
                    total=2,
                    total_page=2,
                ))
            return FakeResponse(200, document=_products(
                [{"slug": "chatgpt-plus", "title": {"zh-CN": "ChatGPT Plus 成品号"}}],
                page=2,
                total=2,
                total_page=2,
            ))
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr("ldxp_crawler.dujiao_discovery.validate_public_url", lambda url: None)
    verifier = DujiaoVerifier(FakeSession(handler), timeout=5, request_interval=0, max_pages=3)
    result = verifier.verify(
        "https://shop.example.com/buy/20",
        discovered_by="seed",
        keywords=("chatgpt", "claude"),
    )

    assert result.origin == "https://shop.example.com"
    assert result.discovered_url == "https://shop.example.com/buy/20"
    assert result.api_verified is True
    assert result.product_count == 2
    assert result.status == "pending_review"
    assert result.fingerprints == ["dujiao-next", "featured-products"]
    assert result.matched_products == [{
        "slug": "chatgpt-plus",
        "name": "ChatGPT Plus 成品号",
        "url": "https://shop.example.com/products/chatgpt-plus",
        "matched_keywords": ["chatgpt"],
    }]


def test_white_label_site_with_matching_api_and_ai_product_enters_review(monkeypatch):
    def handler(url: str, _kwargs: dict):
        if urlsplit(url).path == "/":
            return FakeResponse(200, text="<title>Example Store</title><main>ordinary storefront</main>")
        return FakeResponse(200, document=_products([
            {"slug": "chatgpt", "title": {"en-US": "ChatGPT Plus"}},
        ]))

    monkeypatch.setattr("ldxp_crawler.dujiao_discovery.validate_public_url", lambda url: None)
    result = DujiaoVerifier(FakeSession(handler), timeout=5, request_interval=0).verify(
        "https://shop.example.com",
        discovered_by="bing",
    )
    assert result.status == "pending_review"
    assert result.api_verified is True
    assert result.fingerprints == []
    assert result.site_name == "Example Store"


@pytest.mark.parametrize(
    ("items", "expected_status"),
    [
        ([], "no_products"),
        ([{"slug": "vpn", "title": {"en-US": "VPN monthly"}}], "no_match"),
    ],
)
def test_verifier_keeps_nonqualifying_products_out_of_review(monkeypatch, items, expected_status):
    def handler(url: str, _kwargs: dict):
        if urlsplit(url).path == "/":
            return FakeResponse(200, text="Dujiao-Next Featured Products")
        return FakeResponse(200, document=_products(items, total_page=0 if not items else 1))

    monkeypatch.setattr("ldxp_crawler.dujiao_discovery.validate_public_url", lambda url: None)
    result = DujiaoVerifier(FakeSession(handler), timeout=5, request_interval=0).verify(
        "https://shop.example.com",
        discovered_by="bing",
    )
    assert result.api_verified is True
    assert result.status == expected_status


@pytest.mark.parametrize("oversized_path", ["/", "/api/v1/public/products"])
def test_candidate_responses_are_streamed_and_closed_at_size_limit(monkeypatch, oversized_path):
    oversized = FakeResponse(
        200,
        chunks=[b"x" * (1024 * 1024) for _ in range(10)],
    )

    def handler(url: str, _kwargs: dict):
        path = urlsplit(url).path
        if path == oversized_path:
            return oversized
        if path == "/":
            return FakeResponse(200, text="Dujiao-Next")
        return FakeResponse(200, document=_products([]))

    monkeypatch.setattr("ldxp_crawler.dujiao_discovery.validate_public_url", lambda url: None)
    session = FakeSession(handler)
    result = DujiaoVerifier(session, timeout=5, request_interval=0).verify(
        "https://shop.example.com",
        discovered_by="seed",
    )

    assert result.status == "validation_failed"
    assert "exceeds 5 MiB" in result.error
    assert oversized.closed is True
    assert oversized.iterated_chunks == (MAX_RESPONSE_BYTES // (1024 * 1024)) + 1
    assert all(kwargs["stream"] is True for _, kwargs in session.calls)
    assert all(kwargs["allow_redirects"] is False for _, kwargs in session.calls)


def test_bing_queries_and_rss_extraction_preserve_discovery_pages():
    queries = bing_queries(("chatgpt",))
    assert '"Dujiao-Next" "Featured Products"' in queries
    assert '"chatgpt" "Dujiao-Next"' in queries
    rss = """<?xml version="1.0"?><rss><channel>
      <item><link>https://shop.example.com/buy/20</link></item>
      <item><link>https://demo.dujiao-next.com/products/demo</link></item>
    </channel></rss>"""
    assert extract_bing_result_urls(rss.encode("utf-8")) == [
        "https://shop.example.com/buy/20",
        "https://demo.dujiao-next.com/products/demo",
    ]


def test_verified_candidates_are_deduplicated_and_stay_pending_review(tmp_path: Path, monkeypatch):
    db = StateDB(tmp_path / "state.db")
    try:
        def handler(url: str, _kwargs: dict):
            if urlsplit(url).path == "/":
                return FakeResponse(200, text="Dujiao-Next Featured Products")
            return FakeResponse(200, document=_products([
                {"slug": "claude-pro", "title": {"zh-CN": "Claude Pro 月卡"}},
            ]))

        monkeypatch.setattr("ldxp_crawler.dujiao_discovery.validate_public_url", lambda url: None)
        verifier = DujiaoVerifier(FakeSession(handler), timeout=5, request_interval=0)
        discovery = DujiaoDiscovery(
            db,
            verifier,
            logger=logging.getLogger("test"),
            max_new_candidates=10,
            max_processed_candidates=10,
            reverify_stale_hours=24,
        )

        assert discovery.add_url("https://shop.example.com/buy/1", "seed") is True
        assert discovery.add_url("https://shop.example.com/products/claude-pro", "bing:query") is False
        assert len(verifier.session.calls) == 2

        rows = db.list_dujiao_candidates(review_status="pending_review")
        assert len(rows) == 1
        row = rows[0]
        assert json.loads(row["sources"]) == ["seed", "bing:query"]
        assert json.loads(row["discovered_urls"]) == [
            "https://shop.example.com/buy/1",
            "https://shop.example.com/products/claude-pro",
        ]
        assert row["api_verified"] == 1
        assert row["matched_product_count"] == 1
        assert row["status"] == "pending_review"
        assert row["review_status"] == "pending_review"

        assert db.review_dujiao_candidate("https://shop.example.com", "approved", "来源页面已人工确认") is True
        assert discovery.add_url("https://shop.example.com/products/claude-pro", "bing:repeat") is False
        reviewed = db.list_dujiao_candidates()[0]
        assert reviewed["review_status"] == "approved"
        assert reviewed["review_note"] == "来源页面已人工确认"
    finally:
        db.close()


def _insert_old_candidates(db: StateDB, count: int) -> None:
    rows = [
        (
            f"https://old-{index}.example.com",
            "[]",
            "[]",
            "[]",
            0,
            None,
            0,
            "[]",
            "validation_failed",
            "pending_review",
            "2000-01-01T00:00:00+00:00",
            "2000-01-01T00:00:00+00:00",
        )
        for index in range(count)
    ]
    db.conn.executemany(
        """
        INSERT INTO dujiao_candidates(
            origin, discovered_urls, sources, fingerprints, api_verified,
            product_count, matched_product_count, matched_products, status,
            review_status, first_seen_at, last_verified_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    db.conn.commit()


def _valid_verifier(monkeypatch) -> DujiaoVerifier:
    def handler(url: str, _kwargs: dict):
        if urlsplit(url).path == "/":
            return FakeResponse(200, text="<title>Stable Store</title>")
        return FakeResponse(200, document=_products([
            {"slug": "claude-pro", "title": {"en-US": "Claude Pro"}},
        ]))

    monkeypatch.setattr("ldxp_crawler.dujiao_discovery.validate_public_url", lambda url: None)
    return DujiaoVerifier(FakeSession(handler), timeout=5, request_interval=0)


def test_run_quotas_ignore_historical_candidate_total(tmp_path: Path, monkeypatch):
    db = StateDB(tmp_path / "quota.db")
    try:
        _insert_old_candidates(db, 500)
        discovery = DujiaoDiscovery(
            db,
            _valid_verifier(monkeypatch),
            logger=logging.getLogger("test"),
            max_new_candidates=1,
            max_processed_candidates=501,
            reverify_stale_hours=24,
        )

        assert discovery.reverify_stale() == 500
        assert discovery.add_url("https://new.example.com", "seed") is True
        assert db.dujiao_candidate_count() == 501
        assert discovery.processed_count == 501
        assert discovery.new_candidate_count == 1
    finally:
        db.close()


def test_new_and_processed_quotas_apply_independently(tmp_path: Path, monkeypatch):
    db = StateDB(tmp_path / "independent.db")
    try:
        _insert_old_candidates(db, 1)
        discovery = DujiaoDiscovery(
            db,
            _valid_verifier(monkeypatch),
            logger=logging.getLogger("test"),
            max_new_candidates=1,
            max_processed_candidates=3,
            reverify_stale_hours=24,
        )
        assert discovery.add_url("https://new-1.example.com", "seed") is True
        assert discovery.add_url("https://new-2.example.com", "seed") is False
        assert discovery.add_url("https://old-0.example.com", "stale") is False
        assert discovery.processed_count == 2

        processed_limited = DujiaoDiscovery(
            db,
            _valid_verifier(monkeypatch),
            logger=logging.getLogger("test"),
            max_new_candidates=10,
            max_processed_candidates=1,
            reverify_stale_hours=0,
        )
        assert processed_limited.add_url("https://new-3.example.com", "seed") is True
        assert processed_limited.add_url("https://new-4.example.com", "seed") is False
        assert processed_limited.processed_count == 1
    finally:
        db.close()


def test_approved_verification_failure_requires_re_review_and_manual_states_are_sticky(tmp_path: Path):
    db = StateDB(tmp_path / "review.db")
    try:
        for label, decision in (
            ("approved", "approved"),
            ("identity", "approved"),
            ("rejected", "rejected"),
            ("disabled", "disabled"),
        ):
            origin = f"https://{label}.example.com"
            db.upsert_dujiao_candidate(DujiaoVerificationResult(
                origin=origin,
                discovered_by="seed",
                discovered_url=origin,
                status="pending_review",
                api_verified=True,
                product_count=1,
                matched_products=[{"slug": "gpt", "name": "GPT"}],
                site_name="Stable Store",
            ))
            assert db.review_dujiao_candidate(origin, decision) is True

        db.upsert_dujiao_candidate(DujiaoVerificationResult(
            origin="https://approved.example.com",
            discovered_by="stale-reverify",
            discovered_url="https://approved.example.com",
            status="validation_failed",
            error="candidate redirected to a different origin",
        ))
        db.upsert_dujiao_candidate(DujiaoVerificationResult(
            origin="https://identity.example.com",
            discovered_by="stale-reverify",
            discovered_url="https://identity.example.com",
            status="pending_review",
            api_verified=True,
            product_count=1,
            matched_products=[{"slug": "gpt", "name": "GPT"}],
            site_name="Different Store",
        ))
        for label in ("rejected", "disabled"):
            db.upsert_dujiao_candidate(DujiaoVerificationResult(
                origin=f"https://{label}.example.com",
                discovered_by="stale-reverify",
                discovered_url=f"https://{label}.example.com",
                status="pending_review",
                api_verified=True,
                product_count=1,
                matched_products=[{"slug": "gpt", "name": "GPT"}],
                site_name="Recovered Store",
            ))

        rows = {row["origin"]: row for row in db.list_dujiao_candidates()}
        approved = rows["https://approved.example.com"]
        assert approved["review_status"] == "needs_re_review"
        assert "redirected to a different origin" in approved["re_review_reason"]
        identity = rows["https://identity.example.com"]
        assert identity["review_status"] == "needs_re_review"
        assert "site identity changed" in identity["re_review_reason"]
        assert rows["https://rejected.example.com"]["review_status"] == "rejected"
        assert rows["https://disabled.example.com"]["review_status"] == "disabled"
    finally:
        db.close()


def test_existing_dujiao_table_migrates_to_standard_review_states(tmp_path: Path):
    path = tmp_path / "legacy.db"
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE dujiao_candidates (
            origin TEXT PRIMARY KEY,
            discovered_urls TEXT NOT NULL DEFAULT '[]',
            sources TEXT NOT NULL DEFAULT '[]',
            fingerprints TEXT NOT NULL DEFAULT '[]',
            api_verified INTEGER NOT NULL DEFAULT 0,
            product_count INTEGER,
            matched_product_count INTEGER NOT NULL DEFAULT 0,
            matched_products TEXT NOT NULL DEFAULT '[]',
            status TEXT NOT NULL DEFAULT 'validation_failed',
            review_status TEXT NOT NULL DEFAULT 'not_eligible',
            review_note TEXT,
            reviewed_at TEXT,
            first_seen_at TEXT NOT NULL,
            last_verified_at TEXT NOT NULL,
            last_error TEXT
        )
        """
    )
    conn.execute(
        """
        INSERT INTO dujiao_candidates(origin, status, review_status, first_seen_at, last_verified_at)
        VALUES ('https://legacy.example.com', 'no_match', 'not_eligible', ?, ?)
        """,
        ("2000-01-01T00:00:00+00:00", "2000-01-01T00:00:00+00:00"),
    )
    conn.commit()
    conn.close()

    db = StateDB(path)
    try:
        row = db.get_dujiao_candidate("https://legacy.example.com")
        assert row is not None
        assert row["review_status"] == "pending_review"
        assert "site_name" in row.keys()
        assert "re_review_reason" in row.keys()
    finally:
        db.close()
