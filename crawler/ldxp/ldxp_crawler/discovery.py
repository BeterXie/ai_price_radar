from __future__ import annotations

import json
import logging
import random
import time
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional, Sequence

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .db import StateDB
from .utils import extract_shop_token, extract_shop_urls, merge_unique, normalize_shop_url

SOURCE_SCORES = {
    "seed": 100,
    "bing_keyword": 90,
    "bing_external": 80,
    "bing_broad": 60,
    "commoncrawl": 40,
    "wayback": 10,
}


def build_session(user_agent: str, retries: int = 2) -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=retries,
        connect=retries,
        read=retries,
        status=retries,
        backoff_factor=0.8,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=5, pool_maxsize=5)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(
        {
            "User-Agent": user_agent,
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.5",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
    )
    return session


class Discovery:
    def __init__(
        self,
        db: StateDB,
        session: requests.Session,
        *,
        timeout: float,
        max_discovered: int,
        logger: logging.Logger,
    ):
        self.db = db
        self.session = session
        self.timeout = timeout
        self.max_discovered = max_discovered
        self.logger = logger

    def reached_limit(self) -> bool:
        return self.max_discovered > 0 and self.db.candidate_count() >= self.max_discovered

    def add_url(self, url: str, source: str, score: int) -> bool:
        normalized = normalize_shop_url(url)
        token = extract_shop_token(normalized or "")
        if not normalized or not token:
            return False
        inserted = self.db.upsert_candidate(token, normalized, source, score)
        if inserted:
            self.logger.info("发现店铺 %-20s 分数=%s 来源=%s", token, score, source[:100])
        return inserted

    def from_seeds(self, seeds: Sequence[str], seed_file: Optional[Path]) -> int:
        values = list(seeds)
        if seed_file and seed_file.exists():
            values.extend(
                line.strip()
                for line in seed_file.read_text("utf-8-sig", errors="ignore").splitlines()
                if line.strip() and not line.lstrip().startswith("#")
            )
        found = 0
        for value in values:
            urls = extract_shop_urls(value)
            if not urls:
                normalized = normalize_shop_url(value)
                urls = [normalized] if normalized else []
            for url in urls:
                found += int(self.add_url(url, "seed", SOURCE_SCORES["seed"]))
        return found

    def from_bing(
        self,
        keywords: Sequence[str],
        *,
        pages: int,
        count: int,
        broad_shards: int,
        delay: float,
    ) -> int:
        queries: list[tuple[str, str, int]] = []
        for keyword in keywords:
            queries.extend(
                [
                    (f'site:pay.ldxp.cn/shop "{keyword}"', "bing_keyword", 90),
                    (f'site:www.ldxp.cn/shop "{keyword}"', "bing_keyword", 90),
                    (f'"pay.ldxp.cn/shop" "{keyword}"', "bing_external", 80),
                    (f'"www.ldxp.cn/shop" "{keyword}"', "bing_external", 80),
                ]
            )
        if broad_shards > 0:
            for shard in list("abcdefghijklmnopqrstuvwxyz0123456789")[: min(36, broad_shards)]:
                queries.append((f'"pay.ldxp.cn/shop" {shard}', "bing_broad", 60))

        found = 0
        seen_queries: set[str] = set()
        for query, source_type, score in queries:
            if query in seen_queries:
                continue
            seen_queries.add(query)
            if self.reached_limit():
                break
            for page in range(max(1, pages)):
                first = 1 + page * count
                params = {
                    "q": query,
                    "format": "rss",
                    "count": min(max(count, 10), 50),
                    "first": first,
                    "setlang": "zh-Hans",
                }
                url = "https://www.bing.com/search?" + urllib.parse.urlencode(params)
                try:
                    response = self.session.get(url, timeout=self.timeout)
                except requests.RequestException as exc:
                    self.logger.warning("Bing 请求失败：%s", exc)
                    break
                if response.status_code != 200:
                    self.logger.warning("Bing HTTP %s：%s", response.status_code, query)
                    break

                page_urls = extract_shop_urls(response.text)
                try:
                    root = ET.fromstring(response.content)
                    for item in root.findall(".//item"):
                        fields = "\n".join(
                            [item.findtext("link") or "", item.findtext("title") or "", item.findtext("description") or ""]
                        )
                        page_urls.extend(extract_shop_urls(fields))
                except ET.ParseError:
                    pass
                page_urls = merge_unique(page_urls)
                if not page_urls:
                    break
                for shop_url in page_urls:
                    found += int(self.add_url(shop_url, f"{source_type}:{query}", score))
                    if self.reached_limit():
                        break
                time.sleep(max(0.0, delay) + random.uniform(0, 0.4))
        return found

    def from_commoncrawl(self, index_count: int) -> int:
        found = 0
        try:
            response = self.session.get("https://index.commoncrawl.org/collinfo.json", timeout=self.timeout)
            response.raise_for_status()
            indexes = response.json()
        except (requests.RequestException, ValueError) as exc:
            self.logger.warning("Common Crawl 索引列表失败：%s", exc)
            return 0

        for index in indexes[: max(0, index_count)]:
            if self.reached_limit():
                break
            api = index.get("cdx-api")
            if not api:
                continue
            params = [
                ("url", "pay.ldxp.cn/shop/*"),
                ("output", "json"),
                ("filter", "status:200"),
                ("filter", "mime:text/html"),
                ("collapse", "urlkey"),
            ]
            try:
                with self.session.get(api, params=params, timeout=max(self.timeout, 60), stream=True) as response:
                    if response.status_code != 200:
                        self.logger.warning("Common Crawl %s HTTP %s", index.get("id"), response.status_code)
                        continue
                    for raw_line in response.iter_lines(decode_unicode=True):
                        if not raw_line:
                            continue
                        try:
                            row = json.loads(raw_line)
                        except json.JSONDecodeError:
                            continue
                        if self.add_url(row.get("url", ""), f"commoncrawl:{index.get('id', '')}", 40):
                            found += 1
                        if self.reached_limit():
                            break
            except requests.RequestException as exc:
                self.logger.warning("Common Crawl %s 失败：%s", index.get("id"), exc)
        return found

    def from_wayback(self) -> int:
        params = [
            ("url", "pay.ldxp.cn/shop/*"),
            ("output", "json"),
            ("fl", "original"),
            ("filter", "statuscode:200"),
            ("filter", "mimetype:text/html"),
            ("collapse", "urlkey"),
        ]
        found = 0
        try:
            response = self.session.get(
                "https://web.archive.org/cdx/search/cdx",
                params=params,
                timeout=max(self.timeout, 90),
            )
            if response.status_code != 200:
                self.logger.warning("Wayback HTTP %s", response.status_code)
                return 0
            rows = response.json()
            iterable = rows[1:] if rows and isinstance(rows[0], list) else rows
            for row in iterable:
                url = row[0] if isinstance(row, list) and row else ""
                if self.add_url(url, "wayback", 10):
                    found += 1
                if self.reached_limit():
                    break
        except (requests.RequestException, ValueError) as exc:
            self.logger.warning("Wayback 失败：%s", exc)
        return found
