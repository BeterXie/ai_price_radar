from __future__ import annotations

import json
import logging
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
import requests

from ldxp_crawler.source_discovery import (
    DiscoveryBridge,
    DiscoveryBridgeError,
    DiscoveryBudget,
    DiscoveryRunner,
    candidate_key_for,
    normalize_candidate_url,
    platform_hint_for_candidate,
)
from ldxp_crawler.source_discovery.bing import BingAdapter, extract_bing_result_urls
from ldxp_crawler.source_discovery.commoncrawl import CommonCrawlAdapter
from ldxp_crawler.source_discovery.github import GitHubAdapter, normalize_github_homepage
from ldxp_crawler.source_discovery.keywords import all_keywords, bing_16688_queries, bing_woocommerce_queries
from ldxp_crawler.source_discovery.platform_16688 import Platform16688Adapter
from ldxp_crawler.source_discovery.seed import SeedAdapter
from ldxp_gpt_crawler import build_parser


class FakeResponse:
    def __init__(self, status_code: int, *, text: str = "", document=None, body: bytes | None = None, headers=None):
        self.status_code = status_code
        self.headers = headers or {}
        self.text = text
        self.body = body if body is not None else json.dumps(document or {}).encode("utf-8")
        self.closed = False
        self.iterated = 0

    def iter_content(self, chunk_size: int):
        for chunk in (self.body[i:i + chunk_size] for i in range(0, len(self.body), chunk_size)):
            self.iterated += 1
            yield chunk

    def close(self):
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()

    def iter_lines(self, decode_unicode: bool = True):
        for line in self.body.decode("utf-8").splitlines():
            yield line

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    @property
    def content(self):
        return self.body

    def json(self):
        return json.loads(self.body.decode("utf-8"))


class FakeSession:
    def __init__(self, handler):
        self.handler = handler
        self.calls: list[tuple[str, dict]] = []

    def get(self, url: str, **kwargs):
        self.calls.append((url, kwargs))
        return self.handler(url, kwargs)

    def post(self, url: str, **kwargs):
        self.calls.append((url, kwargs))
        return self.handler(url, kwargs)


class FakeBridge:
    def __init__(self):
        self.enabled = True
        self.runs: list[dict] = []
        self.upserts: list[list[dict]] = []
        self.finished: list[dict] = []
        self.run_id = 1

    def create_run(self, *, trigger: str, adapters: list[str]) -> int:
        self.runs.append({"trigger": trigger, "adapters": adapters})
        self.run_id += 1
        return self.run_id - 1

    def batch_upsert(self, items: list[dict]) -> list[dict]:
        self.upserts.append(items)
        return [{"candidate_id": index, "is_new": True, "merged": False} for index in range(len(items))]

    def finish_run(self, run_id: int, payload: dict) -> None:
        self.finished.append({"run_id": run_id, **payload})

    def upsert(self, **kwargs) -> dict:
        self.upserts.append([kwargs])
        return {"candidate_id": 1, "is_new": True, "merged": False}


def make_runner(bridge=None, adapters=None, **kwargs):
    bridge = bridge or FakeBridge()
    budget = DiscoveryBudget(request_interval_seconds=0)
    return DiscoveryRunner(
        adapters or [],
        bridge,
        logger=logging.getLogger("test-source-discovery"),
        budget=budget,
        keywords=("chatgpt", "claude"),
        **kwargs,
    )


def test_normalization_and_candidate_keys():
    assert normalize_candidate_url("http://shop.example.com") == "https://shop.example.com/"
    assert normalize_candidate_url("https://shop.example.com:443/store") == "https://shop.example.com/store"
    for bad in (
        "https://user:pass@shop.example.com",
        "https://shop.example.com:8443",
        "https://shop.example.com/#frag",
        "https://localhost",
        "https://127.0.0.1",
        "https://10.0.0.1",
        "https://shop.local",
        "https://shop.internal",
        "javascript:alert(1)",
    ):
        with pytest.raises(ValueError):
            normalize_candidate_url(bad)
    assert candidate_key_for("https://shop.example.com/", "dujiao_next") == "https://shop.example.com"
    assert candidate_key_for("https://shop.example.com/", "woocommerce") == "https://shop.example.com"
    key = candidate_key_for("https://shop.example.com/product-sitemap.xml", "schema_org")
    assert key.startswith("sha256:") is False and len(key) == 64
    assert candidate_key_for("https://shop.example.com/product-sitemap.xml", "unknown") == key


def test_keywords_are_deduplicated_and_include_brand_and_chinese_terms():
    keywords = all_keywords()
    assert len(keywords) == len(set(keywords))
    assert "chatgpt" in keywords and "成品号" in keywords and "codex" in keywords
    queries = bing_woocommerce_queries(("chatgpt",))
    assert '"ChatGPT Plus" "add to cart"' in queries
    assert '"chatgpt" "add to cart"' in queries
    assert 'site:16688.com.cn/shop "ChatGPT"' in bing_16688_queries()


def test_bing_16688_queries_coverage():
    """Verify that bing_16688_queries() covers all high-value discovery terms."""
    queries = bing_16688_queries()

    # No duplicates
    assert len(queries) == len(set(queries))

    joined = " ".join(queries)

    # Priority 1 – brand / product names
    assert "ChatGPT" in joined
    assert "Codex" in joined
    assert "OpenAI" in joined
    assert "Claude" in joined
    assert "Gemini" in joined
    assert "Grok" in joined

    # Priority 3 – service / fulfilment keywords
    assert "接码" in joined
    assert "验证码" in joined
    assert "成品号" in joined

    # All queries must be scoped to the official 16688 shop domain
    for query in queries:
        assert "site:16688.com.cn/shop" in query, (
            f"Query does not restrict to 16688 shop domain: {query!r}"
        )


def test_16688_shop_urls_get_a_platform_hint():
    assert platform_hint_for_candidate("https://www.16688.com.cn/shop/HARVEY") == "16688"
    assert platform_hint_for_candidate("https://www.16688.com.cn/goods/G1") == "unknown"


def test_seed_adapter_reads_file_and_skips_comments(tmp_path: Path):
    seed_file = tmp_path / "seeds.txt"
    seed_file.write_text("# comment\n\nhttps://shop.example.com/\nhttps://shop.two.example.com\n", encoding="utf-8")
    adapter = SeedAdapter([], seed_file)
    values = list(adapter.discover(keywords=(), budget=DiscoveryBudget()))
    assert [item.url for item in values] == [
        "https://shop.example.com/",
        "https://shop.two.example.com/",
    ]
    assert all(item.discovered_by == "seed" for item in values)


def test_bing_adapter_parses_rss_and_skips_invalid_urls():
    rss = """<?xml version="1.0"?><rss><channel>
      <item><link>https://shop.example.com/products/chatgpt</link></item>
      <item><link>https://user:pass@bad.example.com</link></item>
      <item><link>http://insecure.example.com</link></item>
    </channel></rss>"""
    assert extract_bing_result_urls(rss.encode("utf-8")) == [
        "https://shop.example.com/products/chatgpt",
        "https://insecure.example.com/",
    ]


def test_bing_adapter_bounds_pages_and_queries():
    calls = 0

    def handler(url: str, _kwargs: dict):
        nonlocal calls
        calls += 1
        assert urlsplit(url).netloc == "www.bing.com"
        return FakeResponse(200, text="")

    adapter = BingAdapter(FakeSession(handler), timeout=3)
    budget = DiscoveryBudget(max_bing_pages=2, max_bing_count=10, request_interval_seconds=0)
    results = list(adapter.discover(keywords=("chatgpt",), budget=budget))
    assert results == []
    assert calls <= 2 * len(set(bing_woocommerce_queries(("chatgpt",)) + [
        '"ChatGPT Plus" "priceCurrency"',
        '"Claude Pro" "InStock"',
        '"Gemini Advanced" "Product"',
        '"OpenAI API" "AggregateOffer"',
        '"SuperGrok" "price"',
        '"chatgpt" "Product" "price"',
    ] + bing_16688_queries(("chatgpt",))))


def test_bing_adapter_discovers_16688_shop_pages_with_platform_hint():
    query = bing_16688_queries()[0]
    rss = b'''<?xml version="1.0"?><rss><channel>
      <item><link>https://www.16688.com.cn/shop/HARVEY</link></item>
    </channel></rss>'''

    def handler(url: str, _kwargs: dict):
        current_query = parse_qs(urlsplit(url).query)["q"][0]
        return FakeResponse(200, body=rss if current_query == query else b"")

    adapter = BingAdapter(FakeSession(handler), timeout=3)
    results = list(adapter.discover(keywords=(), budget=DiscoveryBudget(max_bing_pages=1, max_bing_count=10, request_interval_seconds=0)))
    assert results[0].url == "https://www.16688.com.cn/shop/HARVEY"
    assert results[0].platform_hint == "16688"


def test_github_adapter_token_and_rate_limit_behavior(tmp_path: Path):
    calls: list[tuple[str, dict]] = []

    def handler(url: str, kwargs: dict):
        calls.append((url, kwargs))
        return FakeResponse(
            403,
            document={"message": "rate limited"},
            headers={"X-RateLimit-Remaining": "0"},
        )

    session = FakeSession(handler)
    adapter = GitHubAdapter(session, timeout=3)
    budget = DiscoveryBudget(
        max_github_pages=2,
        max_github_count=10,
        max_github_candidates=10,
        request_interval_seconds=0,
        github_token="ghp_secret",
    )
    assert list(adapter.discover(keywords=(), budget=budget)) == []
    assert len(calls) == 1
    url, kwargs = calls[0]
    assert url.startswith("https://api.github.com")
    assert kwargs["headers"]["Authorization"] == "Bearer ghp_secret"
    assert kwargs["allow_redirects"] is False

    anonymous = GitHubAdapter(FakeSession(handler), timeout=3)
    anonymous_budget = DiscoveryBudget(
        max_github_pages=1,
        max_github_count=10,
        max_github_candidates=10,
        request_interval_seconds=0,
    )
    list(anonymous.discover(keywords=(), budget=anonymous_budget))
    assert "Authorization" not in anonymous.session.calls[0][1]["headers"]


def test_github_homepage_excludes_github_and_examples():
    assert normalize_github_homepage("https://github.com/owner/repo") is None
    assert normalize_github_homepage("https://example.com") is None
    assert normalize_github_homepage("https://127.0.0.1") is None
    assert normalize_github_homepage("https://shop.valid.test/store") == "https://shop.valid.test/store"


def test_commoncrawl_adapter_uses_cdx_without_warc(tmp_path: Path):
    lines = "\n".join([
        json.dumps({"url": "https://pay.ldxp.cn/shop/TOKEN1"}),
        json.dumps({"url": "https://pay.ldxp.cn/shop/TOKEN2"}),
        json.dumps({"url": "https://user:pass@bad.example"}),
        "not-json",
    ])

    def handler(url: str, kwargs: dict):
        if url == "https://index.commoncrawl.org/collinfo.json":
            return FakeResponse(200, document=[{"id": "CC-MAIN-1", "cdx-api": "https://index.commoncrawl.org/CC-MAIN-1-index"}])
        assert "CC-MAIN-1" in url
        params = list(kwargs["params"])
        assert ("output", "json") in params
        assert ("filter", "status:200") in params
        assert ("filter", "mime:text/html") in params
        pattern = dict(kwargs["params"])["url"]
        return FakeResponse(200, body=lines.encode("utf-8") if pattern == "pay.ldxp.cn/shop/*" else b"")

    adapter = CommonCrawlAdapter(FakeSession(handler), timeout=3)
    results = list(adapter.discover(keywords=(), budget=DiscoveryBudget(max_cc_indexes=1, max_cc_urls=3, request_interval_seconds=0)))
    assert [item.url for item in results] == [
        "https://pay.ldxp.cn/shop/TOKEN1",
        "https://pay.ldxp.cn/shop/TOKEN2",
    ]


def test_commoncrawl_adapter_discovers_16688_shop_pages():
    lines = json.dumps({"url": "https://www.16688.com.cn/shop/HARVEY"})

    def handler(url: str, kwargs: dict):
        if url == "https://index.commoncrawl.org/collinfo.json":
            return FakeResponse(200, document=[{"id": "CC-MAIN-1", "cdx-api": "https://index.commoncrawl.org/CC-MAIN-1-index"}])
        if dict(kwargs["params"])["url"] == "16688.com.cn/shop/*":
            return FakeResponse(200, body=lines.encode("utf-8"))
        return FakeResponse(200, body=b"")

    adapter = CommonCrawlAdapter(FakeSession(handler), timeout=3)
    results = list(adapter.discover(keywords=(), budget=DiscoveryBudget(max_cc_indexes=1, max_cc_urls=2, request_interval_seconds=0)))
    assert len(results) == 1
    assert results[0].platform_hint == "16688"


def test_commoncrawl_adapter_reserves_capacity_for_16688():
    ldxp_lines = "\n".join(
        json.dumps({"url": f"https://pay.ldxp.cn/shop/TOKEN{index}"})
        for index in range(3)
    ).encode("utf-8")
    apex_16688 = json.dumps({"url": "https://16688.com.cn/shop/ALPHA"}).encode("utf-8")
    www_16688 = json.dumps({"url": "https://www.16688.com.cn/shop/BRAVO"}).encode("utf-8")

    def handler(url: str, kwargs: dict):
        if url == "https://index.commoncrawl.org/collinfo.json":
            return FakeResponse(200, document=[{"id": "CC-MAIN-1", "cdx-api": "https://index.commoncrawl.org/CC-MAIN-1-index"}])
        pattern = dict(kwargs["params"])["url"]
        return FakeResponse(200, body={
            "pay.ldxp.cn/shop/*": ldxp_lines,
            "16688.com.cn/shop/*": apex_16688,
            "www.16688.com.cn/shop/*": www_16688,
        }[pattern])

    adapter = CommonCrawlAdapter(FakeSession(handler), timeout=3)
    results = list(adapter.discover(keywords=(), budget=DiscoveryBudget(max_cc_indexes=1, max_cc_urls=4, request_interval_seconds=0)))

    assert [item.url for item in results] == [
        "https://pay.ldxp.cn/shop/TOKEN0",
        "https://pay.ldxp.cn/shop/TOKEN1",
        "https://16688.com.cn/shop/ALPHA",
        "https://www.16688.com.cn/shop/BRAVO",
    ]


def test_16688_source_adapter_resolves_public_goods_to_official_shop_urls():
    def handler(url: str, kwargs: dict):
        if url.endswith("/index/SourceCategory/tree"):
            assert kwargs["json"] == {}
            return FakeResponse(200, document={
                "code": 1,
                "data": {"list": [{"id": 1, "name": "AI与效率"}]},
            })
        if url.endswith("/index/SourceGoods/list"):
            assert kwargs["json"] == {
                "page_no": 1,
                "page_size": 20,
                "source_category_id": 1,
            }
            return FakeResponse(200, document={
                "code": 1,
                "data": {
                    "total": 2,
                    "list": [
                        {"goods_no": "G1", "name": "ChatGPT Plus"},
                        {"goods_no": "G2", "name": "Codex 接码"},
                    ],
                },
            })
        assert url.endswith("/shopApi/goods/detail")
        shop_no = {"G1": "S100", "G2": "S200"}[kwargs["json"]["goods_no"]]
        return FakeResponse(200, document={"code": 1, "data": {"shop_no": shop_no}})

    adapter = Platform16688Adapter(FakeSession(handler), timeout=3)
    results = list(adapter.discover(keywords=(), budget=DiscoveryBudget(request_interval_seconds=0)))

    assert [item.url for item in results] == [
        "https://www.16688.com.cn/shop/S100",
        "https://www.16688.com.cn/shop/S200",
    ]
    assert [item.discovered_by for item in results] == ["16688-source:G1", "16688-source:G2"]
    assert all(item.platform_hint == "16688" for item in results)


def test_16688_source_adapter_prioritizes_ai_and_scans_all_categories():
    list_calls: list[tuple[int, int]] = []
    detail_calls: list[str] = []

    def handler(url: str, kwargs: dict):
        if url.endswith("/index/SourceCategory/tree"):
            return FakeResponse(200, document={
                "code": 1,
                "data": {"list": [
                    {"id": 2, "name": "游戏相关"},
                    {"id": 1, "name": "AI与效率"},
                    {"id": 3, "name": "软件工具"},
                ]},
            })
        if url.endswith("/index/SourceGoods/list"):
            payload = kwargs["json"]
            list_calls.append((payload["source_category_id"], payload["page_no"]))
            items = {
                1: [{"goods_no": "G-AI", "name": "G Plus", "merchant": {"merchant_no": "M1"}}],
                2: [{"goods_no": "G-GAME", "name": "另一商品", "merchant": {"merchant_no": "M1"}}],
                3: [{"goods_no": "G-TOOL", "name": "工具", "merchant": {"merchant_no": "M3"}}],
            }[payload["source_category_id"]]
            return FakeResponse(200, document={"code": 1, "data": {"total": 1, "list": items}})
        assert url.endswith("/shopApi/goods/detail")
        goods_no = kwargs["json"]["goods_no"]
        detail_calls.append(goods_no)
        shop_no = {"G-AI": "S1", "G-TOOL": "S3"}[goods_no]
        return FakeResponse(200, document={"code": 1, "data": {"shop_no": shop_no}})

    adapter = Platform16688Adapter(FakeSession(handler), timeout=3)
    results = list(adapter.discover(
        keywords=(),
        budget=DiscoveryBudget(request_interval_seconds=0),
    ))

    assert [item.url for item in results] == [
        "https://www.16688.com.cn/shop/S1",
        "https://www.16688.com.cn/shop/S3",
    ]
    assert list_calls == [(1, 1), (2, 1), (3, 1)]
    assert detail_calls == ["G-AI", "G-TOOL"]


def test_16688_source_adapter_uses_one_global_page_budget():
    list_calls: list[tuple[int, int]] = []

    def handler(url: str, kwargs: dict):
        if url.endswith("/index/SourceCategory/tree"):
            return FakeResponse(200, document={
                "code": 1,
                "data": {"list": [
                    {"id": 1, "name": "AI与效率"},
                    {"id": 2, "name": "游戏相关"},
                ]},
            })
        if url.endswith("/index/SourceGoods/list"):
            payload = kwargs["json"]
            list_calls.append((payload["source_category_id"], payload["page_no"]))
            goods_no = "G1" if payload["page_no"] == 1 else "G2"
            return FakeResponse(200, document={
                "code": 1,
                "data": {"total": 40, "list": [{"goods_no": goods_no, "name": "商品"}]},
            })
        goods_no = kwargs["json"]["goods_no"]
        return FakeResponse(200, document={"code": 1, "data": {"shop_no": goods_no}})

    adapter = Platform16688Adapter(FakeSession(handler), timeout=3)
    list(adapter.discover(
        keywords=(),
        budget=DiscoveryBudget(max_16688_source_pages=2, request_interval_seconds=0),
    ))

    assert list_calls == [(1, 1), (1, 2)]


def test_runner_submits_batches_deduplicates_and_finishes_run():
    bridge = FakeBridge()

    class AdapterA:
        name = "seed"

        def discover(self, *, keywords, budget):
            yield from [
                __import__("ldxp_crawler.source_discovery.models", fromlist=["DiscoveredCandidate"]).DiscoveredCandidate(
                    "https://shop.example.com/a", "seed", "unknown", ""
                ),
                __import__("ldxp_crawler.source_discovery.models", fromlist=["DiscoveredCandidate"]).DiscoveredCandidate(
                    "https://shop.example.com/b", "seed", "dujiao_next", ""
                ),
                __import__("ldxp_crawler.source_discovery.models", fromlist=["DiscoveredCandidate"]).DiscoveredCandidate(
                    "https://shop.example.com/a", "seed", "unknown", ""
                ),
            ]

    class AdapterB:
        name = "bing"

        def discover(self, *, keywords, budget):
            raise requests.RequestException("bing down")

    runner = DiscoveryRunner(
        [AdapterA(), AdapterB()],
        bridge,
        logger=logging.getLogger("test-source-discovery"),
        budget=DiscoveryBudget(request_interval_seconds=0),
    )
    stats = runner.run()
    assert stats.discovered_raw_count == 3
    assert stats.normalized_count == 2
    assert stats.duplicate_count == 1
    assert stats.new_candidate_count == 2
    assert stats.adapter_stats == {"seed": 2}
    assert "bing" in stats.failure_stats
    assert len(bridge.runs) == 1
    assert bridge.runs[0]["adapters"] == ["seed", "bing"]
    assert bridge.upserts[0][0]["discovered_by"] == "seed"
    assert bridge.upserts[0][0]["run_id"] == 1
    assert bridge.finished[0]["status"] == "partial"
    assert bridge.finished[0]["new_candidate_count"] == 2


def test_runner_survives_run_create_failure():
    class BrokenBridge(FakeBridge):
        def create_run(self, *, trigger, adapters):
            raise DiscoveryBridgeError("api down")

    runner = make_runner(BrokenBridge())
    stats = runner.run()
    assert "run_create" in stats.failure_stats
    assert stats.new_candidate_count == 0


def test_runner_never_submits_without_bridge_configuration():
    bridge = DiscoveryBridge("", "")
    assert bridge.enabled is False
    with pytest.raises(DiscoveryBridgeError):
        bridge.create_run(trigger="manual", adapters=["seed"])


def test_cli_exposes_discover_sources_command(monkeypatch):
    args = build_parser().parse_args(["discover-sources", "--sources", "seed", "--seed", "https://shop.example.com"])
    assert args.command == "discover-sources"
    assert args.sources == "seed"
    assert args.max_raw_urls == 2000
    assert args.max_unique_candidates == 1000
    monkeypatch.setenv("DISCOVERY_API_URL", "http://api:8000")
    monkeypatch.setenv("DISCOVERY_WORKER_KEY", "worker-test")
    env_args = build_parser().parse_args(["discover-sources"])
    assert env_args.api_url == "http://api:8000"
    assert env_args.worker_key == "worker-test"
    assert "16688" in env_args.sources.split(",")
    assert env_args.source_16688_pages == 10
