from __future__ import annotations

import json
import logging
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
import requests

from ldxp_crawler.db import StateDB
from ldxp_crawler.dujiao_discovery import (
    GITHUB_API_ORIGIN,
    GITHUB_MAX_PAGES,
    GITHUB_MAX_RESPONSE_BYTES,
    GITHUB_REPOSITORY_QUERY,
    GITHUB_REPOSITORY_QUERIES,
    DujiaoDiscovery,
    DujiaoVerificationResult,
    normalize_candidate_origin,
    normalize_github_homepage,
)
from ldxp_gpt_crawler import build_parser


class FakeGitHubResponse:
    def __init__(
        self,
        status_code: int = 200,
        *,
        document=None,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ):
        self.status_code = status_code
        self.headers = headers or {}
        self.body = body if body is not None else json.dumps(document or {}).encode("utf-8")
        self.closed = False

    def iter_content(self, chunk_size: int):
        assert chunk_size == 64 * 1024
        yield self.body

    def close(self):
        self.closed = True


class FakeGitHubSession:
    def __init__(self, handler):
        self.handler = handler
        self.calls: list[tuple[str, dict]] = []

    def get(self, url: str, **kwargs):
        self.calls.append((url, kwargs))
        return self.handler(url, kwargs)


class RecordingVerifier:
    def __init__(self, session: FakeGitHubSession):
        self.session = session
        self.timeout = 5.0
        self.calls: list[tuple[str, str, tuple[str, ...]]] = []

    def verify(self, url: str, *, discovered_by: str, keywords):
        origin = normalize_candidate_origin(url)
        assert origin is not None
        self.calls.append((url, discovered_by, tuple(keywords)))
        return DujiaoVerificationResult(
            origin=origin,
            discovered_by=discovered_by,
            discovered_url=url,
            status="pending_review",
            fingerprints=["dujiao-next"],
            api_verified=True,
            product_count=1,
            matched_products=[{
                "slug": "chatgpt",
                "name": "ChatGPT Plus",
                "url": origin + "/products/chatgpt",
                "matched_keywords": ["chatgpt"],
            }],
        )


def make_discovery(db: StateDB, session: FakeGitHubSession) -> tuple[DujiaoDiscovery, RecordingVerifier]:
    verifier = RecordingVerifier(session)
    return DujiaoDiscovery(
        db,
        verifier,  # type: ignore[arg-type]
        logger=logging.getLogger("test-dujiao-github"),
        max_new_candidates=100,
        max_processed_candidates=100,
        reverify_stale_hours=24,
    ), verifier


def github_document(items: list[dict], *, total_count: int) -> dict:
    return {"total_count": total_count, "incomplete_results": False, "items": items}


def test_cli_accepts_github_without_changing_default_sources():
    defaults = build_parser().parse_args(["discover-dujiao"])
    assert defaults.sources == "seed,bing"

    args = build_parser().parse_args([
        "discover-dujiao",
        "--sources", "seed,bing,github",
        "--github-pages", "3",
        "--github-count", "25",
        "--github-timeout", "7",
        "--github-max-candidates", "40",
    ])
    assert args.sources == "seed,bing,github"
    assert args.github_pages == 3
    assert args.github_count == 25
    assert args.github_timeout == 7
    assert args.github_max_candidates == 40


@pytest.mark.parametrize("homepage", [
    "",
    "http://shop.valid.test",
    "https://user:secret@shop.valid.test",
    "https://shop.valid.test/#dashboard",
    "https://shop.valid.test:8443",
    "https://localhost",
    "https://127.0.0.1",
    "https://8.8.8.8",
    "https://github.com/owner/repository",
    "https://api.github.com/repos/owner/repository",
    "https://raw.githubusercontent.com/owner/repository/main/README.md",
    "https://dujiao-next.com",
    "https://www.dujiao-next.com/docs",
    "https://example.com",
    "https://placeholder.example",
])
def test_github_homepage_rejects_noncanonical_or_excluded_urls(homepage: str):
    assert normalize_github_homepage(homepage) is None


def test_github_homepage_normalizes_public_https_443_url():
    assert normalize_github_homepage("https://Shop.Valid.test:443/store?q=repo") == (
        "https://shop.valid.test/store?q=repo"
    )


def test_github_repository_homepages_use_existing_verification_and_dedupe_chain(tmp_path: Path):
    responses = {
        1: FakeGitHubResponse(document=github_document([
            {
                "full_name": "owner/deployment-one",
                "private": False,
                "homepage": "https://Shop.One.test:443/store",
            },
            {
                "full_name": "owner/deployment-one-mirror",
                "private": False,
                "homepage": "https://shop.one.test/products/chatgpt?from=github",
            },
        ], total_count=4)),
        2: FakeGitHubResponse(document=github_document([
            {
                "full_name": "owner/deployment-two",
                "private": False,
                "homepage": "https://shop.two.test",
            },
            {
                "full_name": "owner/source-only",
                "private": False,
                "homepage": "https://github.com/owner/source-only",
            },
        ], total_count=4)),
    }

    def handler(url: str, _kwargs: dict):
        parsed = urlsplit(url)
        assert f"{parsed.scheme}://{parsed.netloc}" == GITHUB_API_ORIGIN
        assert parsed.path == "/search/repositories"
        page = int(parse_qs(parsed.query)["page"][0])
        assert parse_qs(parsed.query)["q"] == [GITHUB_REPOSITORY_QUERY]
        return responses[page]

    db = StateDB(tmp_path / "github.db")
    try:
        session = FakeGitHubSession(handler)
        discovery, verifier = make_discovery(db, session)

        assert discovery.from_github(
            ("chatgpt",),
            pages=2,
            count=2,
            max_candidates=10,
            timeout=4,
        ) == 2

        assert len(session.calls) == 2
        assert len(verifier.calls) == 2
        assert [call[0] for call in verifier.calls] == [
            "https://shop.one.test/store",
            "https://shop.two.test/",
        ]
        for _url, kwargs in session.calls:
            assert kwargs["timeout"] == 4
            assert kwargs["allow_redirects"] is False
            assert kwargs["stream"] is True
            assert kwargs["headers"]["Accept"] == "application/vnd.github+json"
        assert all(response.closed for response in responses.values())

        rows = {row["origin"]: row for row in db.list_dujiao_candidates()}
        assert set(rows) == {"https://shop.one.test", "https://shop.two.test"}
        assert json.loads(rows["https://shop.one.test"]["sources"]) == [
            "github:owner/deployment-one",
            "github:owner/deployment-one-mirror",
        ]
        assert rows["https://shop.one.test"]["api_verified"] == 1
        assert rows["https://shop.one.test"]["status"] == "pending_review"
    finally:
        db.close()


def test_github_candidate_quota_stops_before_requesting_another_page(tmp_path: Path):
    response = FakeGitHubResponse(document=github_document([
        {"full_name": f"owner/repo-{index}", "homepage": f"https://shop-{index}.valid.test"}
        for index in range(3)
    ], total_count=100))
    session = FakeGitHubSession(lambda _url, _kwargs: response)
    db = StateDB(tmp_path / "quota.db")
    try:
        discovery, verifier = make_discovery(db, session)
        assert discovery.from_github(
            (),
            pages=5,
            count=3,
            max_candidates=2,
            timeout=5,
        ) == 2
        assert len(session.calls) == 1
        assert len(verifier.calls) == 2
        assert db.dujiao_candidate_count() == 2
    finally:
        db.close()


def test_github_page_count_has_a_hard_upper_bound(tmp_path: Path):
    def handler(url: str, _kwargs: dict):
        page = int(parse_qs(urlsplit(url).query)["page"][0])
        return FakeGitHubResponse(document=github_document([
            {"full_name": f"owner/repo-{page}", "homepage": f"https://page-{page}.valid.test"},
        ], total_count=1000))

    db = StateDB(tmp_path / "pages.db")
    try:
        session = FakeGitHubSession(handler)
        discovery, verifier = make_discovery(db, session)
        discovery.from_github(
            (),
            pages=GITHUB_MAX_PAGES + 20,
            count=1,
            max_candidates=100,
            timeout=5,
        )
        assert len(session.calls) == GITHUB_MAX_PAGES
        assert len(verifier.calls) == GITHUB_MAX_PAGES
    finally:
        db.close()


@pytest.mark.parametrize("failure", [
    requests.Timeout("timed out"),
    FakeGitHubResponse(403, document={"message": "rate limited"}, headers={"X-RateLimit-Remaining": "0"}),
    FakeGitHubResponse(429, document={"message": "rate limited"}),
    FakeGitHubResponse(500, document={"message": "server error"}),
    FakeGitHubResponse(200, body=b"not-json"),
])
def test_github_api_failures_and_rate_limits_do_not_submit_candidates(tmp_path: Path, failure):
    def handler(_url: str, _kwargs: dict):
        if isinstance(failure, BaseException):
            raise failure
        return failure

    db = StateDB(tmp_path / "failure.db")
    try:
        session = FakeGitHubSession(handler)
        discovery, verifier = make_discovery(db, session)
        assert discovery.from_github((), pages=2, count=10, max_candidates=10, timeout=3) == 0
        assert len(session.calls) == 1
        assert verifier.calls == []
        assert db.dujiao_candidate_count() == 0
    finally:
        db.close()


def test_github_api_response_body_is_bounded_and_closed(tmp_path: Path):
    response = FakeGitHubResponse(
        document={},
        headers={"Content-Length": str(GITHUB_MAX_RESPONSE_BYTES + 1)},
    )
    db = StateDB(tmp_path / "body-limit.db")
    try:
        session = FakeGitHubSession(lambda _url, _kwargs: response)
        discovery, verifier = make_discovery(db, session)
        assert discovery.from_github((), pages=1, count=10, max_candidates=10, timeout=3) == 0
        assert response.closed is True
        assert verifier.calls == []
    finally:
        db.close()


def test_github_token_is_sent_only_to_github_api_and_never_logged(tmp_path: Path, caplog):
    response = FakeGitHubResponse(document=github_document([
        {"full_name": "owner/repo", "homepage": "https://shop.valid.test"},
    ], total_count=1))
    session = FakeGitHubSession(lambda _url, _kwargs: response)
    db = StateDB(tmp_path / "token.db")
    try:
        discovery, verifier = make_discovery(db, session)
        with caplog.at_level(logging.WARNING, logger="test-dujiao-github"):
            assert discovery.from_github(
                ("chatgpt",),
                pages=1,
                count=10,
                max_candidates=10,
                timeout=3,
                github_token="ghp_secret-token",
            ) == 1
        assert len(session.calls) == 1
        url, kwargs = session.calls[0]
        assert url.startswith(GITHUB_API_ORIGIN)
        assert kwargs["headers"]["Authorization"] == "Bearer ghp_secret-token"
        assert verifier.calls
        assert "ghp_secret-token" not in caplog.text
    finally:
        db.close()


def test_github_without_token_omits_authorization_header(tmp_path: Path):
    response = FakeGitHubResponse(document=github_document([
        {"full_name": "owner/repo", "homepage": "https://shop.valid.test"},
    ], total_count=1))
    session = FakeGitHubSession(lambda _url, _kwargs: response)
    db = StateDB(tmp_path / "anonymous.db")
    try:
        discovery, _verifier = make_discovery(db, session)
        discovery.from_github((), pages=1, count=10, max_candidates=10, timeout=3)
        _url, kwargs = session.calls[0]
        assert "Authorization" not in kwargs["headers"]
    finally:
        db.close()


def test_github_queries_share_one_hard_total_page_budget(tmp_path: Path):
    queries_seen: list[str] = []

    def handler(url: str, _kwargs: dict):
        queries_seen.append(parse_qs(urlsplit(url).query)["q"][0])
        page = int(parse_qs(urlsplit(url).query)["page"][0])
        return FakeGitHubResponse(document=github_document([
            {"full_name": f"owner/repo-{page}", "homepage": f"https://page-{page}.valid.test"},
        ], total_count=1000))

    db = StateDB(tmp_path / "query-budget.db")
    try:
        session = FakeGitHubSession(handler)
        discovery, _verifier = make_discovery(db, session)
        discovery.from_github(
            (),
            pages=GITHUB_MAX_PAGES + 20,
            count=1,
            max_candidates=100,
            timeout=5,
        )
        assert len(session.calls) == GITHUB_MAX_PAGES
        assert queries_seen[0] == GITHUB_REPOSITORY_QUERY
        assert set(queries_seen) <= set(GITHUB_REPOSITORY_QUERIES)
    finally:
        db.close()


def test_github_token_error_path_does_not_leak_token_into_logs(tmp_path: Path, caplog):
    def handler(_url: str, _kwargs: dict):
        return FakeGitHubResponse(403, document={"message": "rate limited"}, headers={"X-RateLimit-Remaining": "0"})

    db = StateDB(tmp_path / "token-error.db")
    try:
        session = FakeGitHubSession(handler)
        discovery, _verifier = make_discovery(db, session)
        with caplog.at_level(logging.WARNING, logger="test-dujiao-github"):
            assert discovery.from_github(
                (),
                pages=2,
                count=10,
                max_candidates=10,
                timeout=3,
                github_token="ghp_secret-token",
            ) == 0
        assert len(session.calls) == 1
        assert "ghp_secret-token" not in caplog.text
    finally:
        db.close()


def test_cli_github_token_defaults_to_environment_and_can_be_overridden(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_env-token")
    args = build_parser().parse_args(["discover-dujiao"])
    assert args.github_token == "ghp_env-token"
    explicit = build_parser().parse_args([
        "discover-dujiao",
        "--github-token", "ghp_explicit-token",
    ])
    assert explicit.github_token == "ghp_explicit-token"
