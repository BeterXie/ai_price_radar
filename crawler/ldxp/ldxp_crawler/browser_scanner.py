from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional, Sequence

from .models import ProductMatch, ShopScanResult
from .public_dom_scanner import PublicDomScanner


def normalize_identity(value: str) -> str:
    return re.sub(r"[\s_.\-—|/\\]+", "", value.casefold())


def has_target_brand(title: str, category: str = "") -> bool:
    title_identity = normalize_identity(title)
    category_identity = normalize_identity(category)
    x_premium = (
        "premium" in title_identity and "twitter" in title_identity
    ) or (
        "推特" in title_identity and any(marker in title_identity for marker in ("会员", "蓝v", "蓝标"))
    )
    if x_premium:
        return True
    target_markers = (
        "chatgpt", "openai", "gpt", "chatplus", "codex", "claude", "gemini",
        "googleoneai", "supergrok", "grok", "xai", "xpremium", "twitterblue",
    )
    implicit_markers = ("成品", "半成品", "首登")
    non_target_plus = ("百度", "网盘", "小红书", "加速器", "梯子", "夸克", "迅雷", "youtube", "netflix", "spotify", "office", "wps")
    if any(marker in title_identity for marker in target_markers):
        return True
    implicit_chatgpt = (
        "plus" in title_identity
        and any(marker in title_identity for marker in implicit_markers)
        and not any(marker in title_identity for marker in non_target_plus)
    )
    if implicit_chatgpt:
        return True
    category_commerce = ("plus", "pro", "team", "business", "max", "advanced", "ultra", "super", "heavy", "会员", "订阅", "代充", "直充", "充值", "接码", "api", "key", "token", "额度", "成品", "账号", "首登")
    generic_email = ("gmail", "谷歌邮箱", "谷歌邮件", "谷歌账号", "outlook", "hotmail", "icloud", "ic邮箱", "微软邮箱")
    return (
        any(marker in category_identity for marker in target_markers)
        and not any(marker in title_identity for marker in generic_email)
        and any(marker in title_identity for marker in category_commerce)
    )


class BrowserShopScanner:
    """Compatibility wrapper around the anonymous public DOM scanner.

    The v3.7.1 policy removes every high-risk capability that this class used to
    provide: persistent browser profiles, storage state restore, internal
    shop API request templates and sensitive header replay. All scan requests
    now come from a fresh anonymous browser context.
    """

    def __init__(
        self,
        *,
        profile_dir: Path,
        storage_state_path: Path,
        executable_path: Optional[Path],
        headless: bool,
        timeout: float,
        page_wait: float,
        manual_challenge_seconds: int,
        max_pages: int,
        page_size: int,
        fetch_mode: str,
        request_interval: float,
        logger: logging.Logger,
    ):
        # profile_dir / storage_state_path / manual_challenge_seconds / max_pages /
        # page_size / fetch_mode are accepted only for CLI compatibility and are
        # intentionally ignored by the anonymous public DOM scanner.
        self.executable_path = executable_path
        self.timeout = timeout
        self.page_wait = page_wait
        self.request_interval = request_interval
        self.logger = logger
        self._delegate: Optional[PublicDomScanner] = None

    def __enter__(self) -> "BrowserShopScanner":
        self._delegate = PublicDomScanner(
            executable_path=self.executable_path,
            timeout=self.timeout,
            page_wait=self.page_wait,
            request_interval=self.request_interval,
            logger=self.logger,
        )
        self._delegate.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._delegate is not None:
            self._delegate.__exit__(exc_type, exc, tb)
            self._delegate = None

    def scan_shop(self, candidate, keywords: Sequence[str]) -> ShopScanResult:
        if self._delegate is None:
            raise RuntimeError("BrowserShopScanner must be used as a context manager")
        return self._delegate.scan_shop(candidate, keywords)
