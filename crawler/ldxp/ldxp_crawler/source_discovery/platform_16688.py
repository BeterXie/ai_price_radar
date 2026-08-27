from __future__ import annotations

import re
import time
import urllib.parse
from collections.abc import Iterable, Sequence
from typing import Any

import requests

from .models import DiscoveredCandidate, DiscoveryAdapter, DiscoveryBudget
from .normalize import normalize_candidate_url


ORIGIN = "https://www.16688.com.cn"
SOURCE_CATEGORY_TREE_PATH = "/index/SourceCategory/tree"
SOURCE_GOODS_LIST_PATH = "/index/SourceGoods/list"
GOODS_DETAIL_PATH = "/shopApi/goods/detail"
AI_CATEGORY_NAME = "AI与效率"
PAGE_SIZE = 20
MAX_PAGES = 50
CODE_PATTERN = re.compile(r"[A-Za-z0-9._~-]{1,128}")
PUBLIC_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Origin": ORIGIN,
    "Referer": f"{ORIGIN}/source",
}


class Platform16688Adapter(DiscoveryAdapter):
    """Resolve public 16688 source-marketplace goods to official shop URLs."""

    name = "16688"

    def __init__(self, session: requests.Session, *, timeout: float):
        self.session = session
        self.timeout = timeout

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        response = None
        try:
            response = self.session.post(
                f"{ORIGIN}{path}",
                json=payload,
                headers=PUBLIC_HEADERS,
                timeout=self.timeout,
                allow_redirects=False,
            )
            if response.status_code != 200:
                return None
            document = response.json()
        except (requests.RequestException, ValueError):
            return None
        finally:
            if response is not None:
                response.close()
        if not isinstance(document, dict) or document.get("code") != 1:
            return None
        return document

    @staticmethod
    def _category_ids(document: dict[str, Any]) -> list[int | str]:
        data = document.get("data")
        roots = data.get("list") if isinstance(data, dict) else None
        if not isinstance(roots, list):
            return []

        categories: list[tuple[bool, int, int | str]] = []
        seen_ids: set[str] = set()

        def visit(rows: list[object]) -> None:
            for row in rows:
                if not isinstance(row, dict):
                    continue
                category_id = row.get("id")
                if (
                    not isinstance(category_id, (int, str))
                    or isinstance(category_id, bool)
                    or not str(category_id).strip()
                ):
                    category_id = None
                if category_id is not None:
                    key = str(category_id).strip()
                    if key not in seen_ids:
                        seen_ids.add(key)
                        categories.append((
                            str(row.get("name") or "").strip() == AI_CATEGORY_NAME,
                            len(categories),
                            category_id,
                        ))
                children = row.get("children")
                if isinstance(children, list):
                    visit(children)

        visit(roots)
        categories.sort(key=lambda item: (not item[0], item[1]))
        return [item[2] for item in categories]

    @staticmethod
    def _limit(value: int) -> int:
        return min(max(1, int(value)), MAX_PAGES)

    @staticmethod
    def _pause(budget: DiscoveryBudget) -> None:
        time.sleep(max(0.0, budget.request_interval_seconds))

    def discover(
        self,
        *,
        keywords: Sequence[str],
        budget: DiscoveryBudget,
    ) -> Iterable[DiscoveredCandidate]:
        del keywords
        categories = self._post_json(SOURCE_CATEGORY_TREE_PATH, {})
        self._pause(budget)
        if categories is None:
            return
        category_ids = self._category_ids(categories)
        if not category_ids:
            return

        seen_goods: set[str] = set()
        seen_shops: set[str] = set()
        shop_by_merchant: dict[str, str] = {}
        pages_left = self._limit(budget.max_16688_source_pages)

        # The source marketplace exposes products, not a public shop directory.
        # Scan the AI category first, then spend the remaining global page budget
        # on every other public category so one category cannot starve the rest.
        for category_id in category_ids:
            page_no = 1
            while pages_left > 0:
                listing = self._post_json(
                    SOURCE_GOODS_LIST_PATH,
                    {
                        "page_no": page_no,
                        "page_size": PAGE_SIZE,
                        "source_category_id": category_id,
                    },
                )
                pages_left -= 1
                self._pause(budget)
                if listing is None:
                    break
                data = listing.get("data")
                items = data.get("list") if isinstance(data, dict) else None
                if not isinstance(items, list) or not items:
                    break

                for item in items:
                    if not isinstance(item, dict):
                        continue
                    goods_no = str(item.get("goods_no") or "").strip()
                    if CODE_PATTERN.fullmatch(goods_no) is None or goods_no in seen_goods:
                        continue
                    seen_goods.add(goods_no)

                    merchant = item.get("merchant")
                    merchant_no = str(merchant.get("merchant_no") or "").strip() if isinstance(merchant, dict) else ""
                    shop_no = shop_by_merchant.get(merchant_no) if merchant_no else None
                    if shop_no is None:
                        detail = self._post_json(GOODS_DETAIL_PATH, {"goods_no": goods_no})
                        self._pause(budget)
                        shop = detail.get("data") if isinstance(detail, dict) else None
                        shop_no = str(shop.get("shop_no") or "").strip() if isinstance(shop, dict) else ""
                        if CODE_PATTERN.fullmatch(shop_no) is None:
                            continue
                        if merchant_no:
                            shop_by_merchant[merchant_no] = shop_no
                    if shop_no in seen_shops:
                        continue
                    seen_shops.add(shop_no)
                    try:
                        url = normalize_candidate_url(
                            f"{ORIGIN}/shop/{urllib.parse.quote(shop_no, safe='._~-')}"
                        )
                    except (TypeError, ValueError):
                        continue
                    yield DiscoveredCandidate(
                        url=url,
                        discovered_by=f"16688-source:{goods_no}",
                        platform_hint="16688",
                        matched_query=str(item.get("name") or "")[:300],
                    )

                total = data.get("total") if isinstance(data, dict) else None
                try:
                    exhausted = int(total) <= page_no * PAGE_SIZE
                except (TypeError, ValueError):
                    exhausted = len(items) < PAGE_SIZE
                if exhausted:
                    break
                page_no += 1
            if pages_left <= 0:
                return
