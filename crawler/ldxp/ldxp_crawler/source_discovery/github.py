from __future__ import annotations

import ipaddress
import json
import urllib.parse
from collections.abc import Iterable, Sequence
from typing import Any

import requests

from .keywords import GITHUB_HOMEPAGE_QUERIES
from .models import DiscoveredCandidate, DiscoveryAdapter, DiscoveryBudget
from .normalize import normalize_candidate_url, normalize_origin


GITHUB_API_ORIGIN = "https://api.github.com"
GITHUB_MAX_PAGES = 10
GITHUB_MAX_RESPONSE_BYTES = 2 * 1024 * 1024
GITHUB_EXCLUDED_HOSTS = frozenset({
    "github.com",
    "api.github.com",
    "githubusercontent.com",
    "githubassets.com",
    "example.com",
    "example.net",
    "example.org",
})


def normalize_github_homepage(value: Any) -> str | None:
    raw = str(value or "").strip()
    if not raw or any(ord(character) < 32 or ord(character) == 127 for character in raw):
        return None
    try:
        parsed = urllib.parse.urlsplit(raw)
        port = parsed.port
    except ValueError:
        return None
    host = (parsed.hostname or "").casefold().rstrip(".")
    if (
        parsed.scheme.casefold() != "https"
        or not host
        or parsed.username
        or parsed.password
        or parsed.fragment
        or port not in (None, 443)
    ):
        return None
    if (
        host in GITHUB_EXCLUDED_HOSTS
        or any(host.endswith("." + excluded) for excluded in GITHUB_EXCLUDED_HOSTS)
        or host.endswith(".example")
    ):
        return None
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        return None
    try:
        return normalize_candidate_url(raw)
    except (TypeError, ValueError):
        return None


class GitHubAdapter(DiscoveryAdapter):
    name = "github"

    def __init__(self, session: requests.Session, *, timeout: float):
        self.session = session
        self.timeout = timeout

    def discover(
        self,
        *,
        keywords: Sequence[str],
        budget: DiscoveryBudget,
    ) -> Iterable[DiscoveredCandidate]:
        page_limit = min(max(1, budget.max_github_pages), GITHUB_MAX_PAGES)
        per_page = min(max(1, budget.max_github_count), 100)
        candidate_limit = min(max(0, budget.max_github_candidates), 500)
        if candidate_limit == 0:
            return
        submitted_origins: set[str] = set()
        pages_remaining = page_limit
        for query in GITHUB_HOMEPAGE_QUERIES:
            if pages_remaining <= 0:
                break
            stopped = False
            for page in range(1, min(pages_remaining, page_limit) + 1):
                params = {
                    "q": query,
                    "sort": "updated",
                    "order": "desc",
                    "per_page": per_page,
                    "page": page,
                }
                url = GITHUB_API_ORIGIN + "/search/repositories?" + urllib.parse.urlencode(params)
                headers = {
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                }
                if budget.github_token:
                    headers["Authorization"] = f"Bearer {budget.github_token}"
                try:
                    response = self.session.get(
                        url,
                        headers=headers,
                        timeout=self.timeout,
                        allow_redirects=False,
                        stream=True,
                    )
                    chunks: list[bytes] = []
                    total = 0
                    for chunk in response.iter_content(chunk_size=64 * 1024):
                        if not chunk:
                            continue
                        total += len(chunk)
                        if total > GITHUB_MAX_RESPONSE_BYTES:
                            raise ValueError("GitHub API response exceeds size limit")
                        chunks.append(chunk)
                    response.close()
                except (requests.RequestException, OSError, ValueError):
                    stopped = True
                    break
                pages_remaining -= 1
                if response.status_code in {403, 429}:
                    stopped = True
                    break
                if response.status_code != 200:
                    stopped = True
                    break
                try:
                    document = json.loads(b"".join(chunks).decode("utf-8"))
                    items = document.get("items")
                except (UnicodeError, json.JSONDecodeError, AttributeError):
                    stopped = True
                    break
                if not isinstance(items, list):
                    stopped = True
                    break
                for item in items:
                    if not isinstance(item, dict) or item.get("private") is True:
                        continue
                    homepage = normalize_github_homepage(item.get("homepage"))
                    if homepage is None:
                        continue
                    origin = normalize_origin(homepage)
                    if origin in submitted_origins:
                        continue
                    submitted_origins.add(origin)
                    if len(submitted_origins) > candidate_limit:
                        return
                    repository = str(item.get("full_name") or "").strip()[:100]
                    yield DiscoveredCandidate(
                        url=homepage,
                        discovered_by=f"github:{repository}" if repository else "github:homepage",
                        platform_hint="unknown",
                        matched_query=query,
                    )
            if stopped:
                break
