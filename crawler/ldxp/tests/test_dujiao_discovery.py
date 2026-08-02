from __future__ import annotations

import json
import logging
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from ldxp_crawler.db import StateDB
from ldxp_crawler.dujiao_discovery import (
    DujiaoDiscovery,
    DujiaoVerifier,
    bing_queries,
    extract_bing_result_urls,
    is_excluded_origin,
    normalize_candidate_origin,
)
from ldxp_gpt_crawler import build_parser


class FakeResponse:
    def __init__(self, status_code: int, *, text: str = "", document=None, headers=None):
        self.status_code = status_code
        self.text = text
        self._document = document
        self.headers = headers or {}
        self.content = text.encode("utf-8")

    def json(self):
        if self._document is None:
            raise ValueError("not JSON")
        return self._document


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
    review = build_parser().parse_args([
        "review-dujiao",
        "--origin", "https://shop.example.com",
        "--decision", "approve",
    ])
    assert review.command == "review-dujiao"
    assert review.decision == "approve"


def test_verifier_requires_home_fingerprint_api_and_ai_product(monkeypatch):
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


@pytest.mark.parametrize(
    ("home", "items", "expected_status"),
    [
        ("ordinary storefront", [{"slug": "chatgpt", "title": {"en-US": "ChatGPT Plus"}}], "fingerprint_mismatch"),
        ("Dujiao-Next Featured Products", [], "no_products"),
        ("Dujiao-Next Featured Products", [{"slug": "vpn", "title": {"en-US": "VPN monthly"}}], "no_match"),
    ],
)
def test_verifier_keeps_nonqualifying_sites_out_of_review(monkeypatch, home, items, expected_status):
    def handler(url: str, _kwargs: dict):
        if urlsplit(url).path == "/":
            return FakeResponse(200, text=home)
        return FakeResponse(200, document=_products(items, total_page=0 if not items else 1))

    monkeypatch.setattr("ldxp_crawler.dujiao_discovery.validate_public_url", lambda url: None)
    result = DujiaoVerifier(FakeSession(handler), timeout=5, request_interval=0).verify(
        "https://shop.example.com",
        discovered_by="bing",
    )
    assert result.api_verified is True
    assert result.status == expected_status


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
        discovery = DujiaoDiscovery(db, verifier, logger=logging.getLogger("test"), max_candidates=10)

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
