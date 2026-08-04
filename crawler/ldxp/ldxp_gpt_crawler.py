#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Sequence

from ldxp_crawler import __version__
from ldxp_crawler.browser_scanner import BrowserShopScanner
from ldxp_crawler.db import StateDB
from ldxp_crawler.discovery import Discovery, build_session
from ldxp_crawler.dujiao_discovery import (
    DEFAULT_AI_KEYWORDS,
    DujiaoDiscovery,
    DujiaoVerifier,
    normalize_candidate_origin,
)
from ldxp_crawler.exporter import export_results
from ldxp_crawler.intake_bridge import IntakeBridge, IntakeBridgeError
from ldxp_crawler.policy import ApiOriginPolicyChecker, CollectionPolicyGate
from ldxp_crawler.public_dom_scanner import PublicDomScanner
from ldxp_crawler.scheduler import DueShopScheduler
from ldxp_crawler.source_discovery import (
    DiscoveryBridge,
    DiscoveryBridgeError,
    DiscoveryBudget,
    DiscoveryRunner,
)
from ldxp_crawler.source_discovery.bing import BingAdapter
from ldxp_crawler.source_discovery.commoncrawl import CommonCrawlAdapter
from ldxp_crawler.source_discovery.github import GitHubAdapter
from ldxp_crawler.source_discovery.keywords import all_keywords
from ldxp_crawler.source_discovery.seed import SeedAdapter
from ldxp_crawler.utils import extract_shop_token, merge_unique

DEFAULT_KEYWORDS = ["gpt", "chatgpt"]
BLOCK_STATUSES = {"blocked", "challenge_required", "rate_limited"}
PUBLIC_VALIDATION_FAILURE_REASONS = {
    "network_error": "来源暂时无法访问",
    "rate_limited": "来源请求受到限流，请稍后重试",
    "blocked": "来源访问被阻断",
    "challenge_required": "来源需要完成公开验证",
    "parse_error": "来源返回内容无法解析",
    "api_changed": "来源接口格式暂不兼容",
    "failed": "来源验证暂时失败",
}


def make_logger(verbose: bool) -> logging.Logger:
    logger = logging.getLogger("ldxp-crawler")
    logger.handlers.clear()
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", "%H:%M:%S"))
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    return logger


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--db", default="ldxp_crawler.db", help="SQLite 状态文件；兼容 v1 数据库并自动迁移")
    parser.add_argument("--keywords", nargs="+", default=DEFAULT_KEYWORDS, help="匹配关键词")
    parser.add_argument("--timeout", type=float, default=35.0, help="页面/API 超时秒数")
    parser.add_argument(
        "--user-agent",
        default=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
        ),
        help="仅用于公共索引发现；浏览器扫描使用 Chromium 自身 UA",
    )
    parser.add_argument("-v", "--verbose", action="store_true")


def add_discovery_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--sources",
        default="seed,bing,commoncrawl",
        help="逗号分隔：seed,bing,commoncrawl,wayback；Wayback 默认关闭以减少历史失效店铺",
    )
    parser.add_argument("--seed", action="append", default=[], help="种子店铺 URL，可重复")
    parser.add_argument("--seed-file", type=Path, default=Path("seeds.txt"))
    parser.add_argument("--bing-pages", type=int, default=5)
    parser.add_argument("--bing-count", type=int, default=30)
    parser.add_argument("--bing-broad-shards", type=int, default=0, help="0 关闭，最高 36")
    parser.add_argument("--bing-delay", type=float, default=1.5)
    parser.add_argument("--cc-indexes", type=int, default=3)
    parser.add_argument("--max-discovered", type=int, default=10000)


def add_dujiao_discovery_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--sources", default="seed,bing", help="逗号分隔：seed,bing,github")
    parser.add_argument("--seed", action="append", default=[], help="候选页面或店铺 URL，可重复")
    parser.add_argument("--seed-file", type=Path, default=Path("dujiao_seeds.txt"))
    parser.add_argument("--bing-pages", type=int, default=2)
    parser.add_argument("--bing-count", type=int, default=20)
    parser.add_argument("--bing-delay", type=float, default=2.0)
    parser.add_argument("--github-pages", type=int, default=2, help="GitHub 仓库搜索页数，硬上限 10")
    parser.add_argument("--github-count", type=int, default=50, help="每页 GitHub 仓库数，硬上限 100")
    parser.add_argument("--github-timeout", type=float, default=10.0, help="单次 GitHub API 请求超时秒数，硬上限 30")
    parser.add_argument("--github-max-candidates", type=int, default=100, help="本次 GitHub 来源最多提交的唯一 Homepage，硬上限 500；0 关闭")
    parser.add_argument("--github-token", default=os.getenv("GITHUB_TOKEN", ""), help="可选的 GitHub 搜索 Token；留空时不发送 Authorization，且只用于 api.github.com")
    parser.add_argument("--request-interval", type=float, default=2.0, help="候选站公开请求最小间隔")
    parser.add_argument("--max-api-pages", type=int, default=5, help="单个候选最多读取的公开商品页数")
    parser.add_argument("--max-new-candidates", type=int, default=500, help="本次最多新增候选数；0 不限制")
    parser.add_argument("--max-processed-candidates", type=int, default=2000, help="本次最多验证候选数；0 不限制")
    parser.add_argument("--reverify-stale-hours", type=float, default=24.0, help="复验超过该小时数未验证的候选")
    parser.add_argument("--discovery-api-url", default=os.getenv("DISCOVERY_API_URL", ""), help="统一候选池 API 地址")
    parser.add_argument("--discovery-worker-key", default=os.getenv("DISCOVERY_WORKER_KEY", ""), help="统一候选池 Worker Key")


def add_source_discovery_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--sources", default="seed,bing,github,commoncrawl", help="逗号分隔：seed,bing,github,commoncrawl")
    parser.add_argument("--seed", action="append", default=[], help="种子候选 URL，可重复")
    parser.add_argument("--seed-file", type=Path, default=Path("config/discovery/general_seeds.txt"))
    parser.add_argument("--api-url", default=os.getenv("DISCOVERY_API_URL", ""), help="统一候选池 API 地址")
    parser.add_argument("--worker-key", default=os.getenv("DISCOVERY_WORKER_KEY", ""), help="统一候选池 Worker Key")
    parser.add_argument("--trigger", choices=("scheduled", "manual", "deploy"), default="scheduled")
    parser.add_argument("--max-raw-urls", type=int, default=2000)
    parser.add_argument("--max-unique-candidates", type=int, default=1000)
    parser.add_argument("--request-interval", type=float, default=2.0)
    parser.add_argument("--bing-pages", type=int, default=5)
    parser.add_argument("--bing-count", type=int, default=30)
    parser.add_argument("--bing-delay", type=float, default=2.0)
    parser.add_argument("--github-pages", type=int, default=3, help="GitHub 页数，硬上限 10")
    parser.add_argument("--github-count", type=int, default=100, help="每页仓库数，硬上限 100")
    parser.add_argument("--github-max-candidates", type=int, default=300, help="GitHub Homepage 唯一候选上限，硬上限 500；0 关闭")
    parser.add_argument("--github-token", default=os.getenv("GITHUB_TOKEN", ""), help="可选的 GitHub Token，只发送给 api.github.com")
    parser.add_argument("--cc-indexes", type=int, default=2)
    parser.add_argument("--cc-max-urls", type=int, default=500)


def add_scan_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--headless", action="store_true", help="无头运行；首次运行建议不要开启")
    parser.add_argument("--executable-path", type=Path, default=None, help="可选的 Chromium/Chrome 可执行文件")
    parser.add_argument("--browser-profile", type=Path, default=Path("browser_profile"))
    parser.add_argument("--storage-state", type=Path, default=Path("browser_state.json"))
    parser.add_argument("--manual-challenge-seconds", type=int, default=300, help="有头模式等待人工正常验证的秒数")
    parser.add_argument("--page-wait", type=float, default=3.0, help="页面打开后等待前端请求的秒数")
    parser.add_argument("--request-interval", type=float, default=2.0, help="全进程浏览器/API 请求最小间隔")
    parser.add_argument("--max-pages", type=int, default=30)
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--fetch-mode", choices=("all", "keyword"), default="all")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--rescan", action="store_true", help="重新扫描成功过的店铺")
    parser.add_argument("--matched-only", action="store_true", help="只扫描已有命中商品的店铺")
    parser.add_argument("--no-retry-failed", action="store_true")
    parser.add_argument("--retry-blocked", action="store_true", help="重新尝试 blocked/challenge_required")
    parser.add_argument("--circuit-breaker", type=int, default=3, help="连续站点级阻断多少次后停止；0 关闭")
    parser.add_argument("--intake-api-url", default=os.getenv("INTAKE_API_URL", ""), help="收录状态机 API 地址")
    parser.add_argument("--intake-worker-key", default=os.getenv("INTAKE_WORKER_KEY", ""), help="收录 Worker Key")
    parser.add_argument("--intake-claim-limit", type=int, default=20, help="每次扫描前领取的人工申请数量")
    parser.add_argument("--intake-lease-seconds", type=int, default=900, help="人工申请租约秒数")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="链动小铺 GPT/ChatGPT 公开店铺检索器 v2（Chromium 会话版）",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    discover = sub.add_parser("discover", help="发现公开店铺 URL")
    add_common_args(discover)
    add_discovery_args(discover)

    dujiao = sub.add_parser("discover-dujiao", help="发现并验证 Dujiao-Next 公开候选")
    add_common_args(dujiao)
    add_dujiao_discovery_args(dujiao)
    dujiao.set_defaults(user_agent="AI-Price-Radar-Discovery/1.0", timeout=10.0)

    sources = sub.add_parser("discover-sources", help="统一公开来源发现：提交候选到统一候选池")
    add_common_args(sources)
    add_source_discovery_args(sources)
    sources.set_defaults(user_agent="AI-Price-Radar-Discovery/1.0", timeout=10.0)

    dujiao_review = sub.add_parser("review-dujiao", help="记录 Dujiao-Next 候选人工审核决定")
    dujiao_review.add_argument("--db", default="ldxp_crawler.db")
    dujiao_review.add_argument("--origin", required=True, help="候选店铺根地址")
    dujiao_review.add_argument("--decision", required=True, choices=("approve", "reject", "disable"))
    dujiao_review.add_argument("--note", default="", help="可选审核备注")
    dujiao_review.add_argument("-v", "--verbose", action="store_true")
    dujiao_review.set_defaults(keywords=[])

    scan = sub.add_parser("scan", help="使用 Chromium 扫描数据库中的候选店铺")
    add_common_args(scan)
    add_scan_args(scan)

    export = sub.add_parser("export", help="导出 Excel/CSV")
    add_common_args(export)
    export.add_argument("--output-dir", type=Path, default=Path("output"))
    export.add_argument("--prefix", default="ldxp_gpt_results")

    all_cmd = sub.add_parser("all", help="发现、扫描、导出")
    add_common_args(all_cmd)
    add_discovery_args(all_cmd)
    add_scan_args(all_cmd)
    all_cmd.add_argument("--output-dir", type=Path, default=Path("output"))
    all_cmd.add_argument("--prefix", default="ldxp_gpt_results")

    bootstrap = sub.add_parser("bootstrap", help="只打开种子店铺，建立/验证浏览器会话")
    add_common_args(bootstrap)
    add_scan_args(bootstrap)
    bootstrap.set_defaults(limit=1, rescan=True, retry_blocked=True)

    return parser


def run_discovery(args: argparse.Namespace, db: StateDB, logger: logging.Logger) -> None:
    discovery = Discovery(
        db,
        build_session(args.user_agent),
        timeout=args.timeout,
        max_discovered=args.max_discovered,
        logger=logger,
    )
    sources = {x.strip().lower() for x in args.sources.split(",") if x.strip()}
    before = db.candidate_count()
    if "seed" in sources:
        discovery.from_seeds(args.seed, args.seed_file)
    if "bing" in sources and not discovery.reached_limit():
        discovery.from_bing(
            args.keywords,
            pages=max(1, args.bing_pages),
            count=max(10, args.bing_count),
            broad_shards=min(max(0, args.bing_broad_shards), 36),
            delay=max(0.0, args.bing_delay),
        )
    if "commoncrawl" in sources and not discovery.reached_limit():
        discovery.from_commoncrawl(max(0, args.cc_indexes))
    if "wayback" in sources and not discovery.reached_limit():
        discovery.from_wayback()
    logger.info("发现完成：新增 %s 家，累计 %s 家。", db.candidate_count() - before, db.candidate_count())


def run_dujiao_discovery(args: argparse.Namespace, db: StateDB, logger: logging.Logger) -> None:
    session = build_session(args.user_agent, retries=0)
    verifier = DujiaoVerifier(
        session,
        timeout=args.timeout,
        request_interval=args.request_interval,
        max_pages=args.max_api_pages,
    )
    discovery = DujiaoDiscovery(
        db,
        verifier,
        logger=logger,
        max_new_candidates=args.max_new_candidates,
        max_processed_candidates=args.max_processed_candidates,
        reverify_stale_hours=args.reverify_stale_hours,
    )
    sources = {value.strip().casefold() for value in args.sources.split(",") if value.strip()}
    unsupported = sources - {"seed", "bing", "github"}
    if unsupported:
        raise ValueError(f"unsupported Dujiao discovery sources: {', '.join(sorted(unsupported))}")
    filter_keywords = merge_unique([*DEFAULT_AI_KEYWORDS, *args.keywords])
    before = db.dujiao_candidate_count()
    reverified = discovery.reverify_stale(filter_keywords)
    if "seed" in sources:
        discovery.from_seeds(args.seed, args.seed_file, filter_keywords)
    if "bing" in sources and not discovery.reached_limit():
        discovery.from_bing(args.keywords, pages=args.bing_pages, count=args.bing_count, delay=args.bing_delay)
    if "github" in sources and not discovery.reached_limit():
        discovery.from_github(
            args.keywords,
            pages=args.github_pages,
            count=args.github_count,
            max_candidates=args.github_max_candidates,
            timeout=args.github_timeout,
            github_token=args.github_token,
        )
    bridge = DiscoveryBridge(args.discovery_api_url, args.discovery_worker_key, timeout=args.timeout)
    bridged = 0
    bridge_failures = 0
    if bridge.enabled:
        for row in db.list_dujiao_candidates():
            try:
                sources = json.loads(row["sources"])
                matched_products = json.loads(row["matched_products"])
                matched_query = ""
                if isinstance(matched_products, list) and matched_products:
                    matched_query = str(matched_products[0].get("name", "") or "")[:300]
                bridge.upsert(
                    discovered_url=str(row["origin"]),
                    platform_hint="dujiao_next",
                    discovered_by=str(sources[0]) if isinstance(sources, list) and sources else "dujiao-discovery",
                    matched_query=matched_query,
                )
                bridged += 1
            except (DiscoveryBridgeError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                logger.warning("Dujiao 候选桥接失败（保持 SQLite 结果）：%s", type(exc).__name__)
                bridge_failures += 1
        logger.info("Dujiao 候选桥接到统一候选池：%s 个，失败 %s 个。", bridged, bridge_failures)
    pending = db.list_dujiao_candidates(
        review_status="pending_review",
        verification_status="pending_review",
    )
    logger.info(
        "Dujiao 发现完成：处理 %s 个（复验 %s），新增 %s 个，累计 %s 个，待人工审核 %s 个。",
        discovery.processed_count,
        reverified,
        db.dujiao_candidate_count() - before,
        db.dujiao_candidate_count(),
        len(pending),
    )
    for row in pending:
        print(json.dumps({
            "origin": row["origin"],
            "discovered_urls": json.loads(row["discovered_urls"]),
            "discovered_by": json.loads(row["sources"]),
            "fingerprints": json.loads(row["fingerprints"]),
            "api_verified": bool(row["api_verified"]),
            "product_count": row["product_count"],
            "matched_products": json.loads(row["matched_products"]),
            "first_seen_at": row["first_seen_at"],
            "last_verified_at": row["last_verified_at"],
            "review_status": row["review_status"],
            "site_name": row["site_name"],
            "re_review_reason": row["re_review_reason"],
        }, ensure_ascii=False))


def run_source_discovery(args: argparse.Namespace, logger: logging.Logger) -> None:
    session = build_session(args.user_agent, retries=0)
    budget = DiscoveryBudget(
        max_raw_urls=max(1, args.max_raw_urls),
        max_unique_candidates=max(1, args.max_unique_candidates),
        request_interval_seconds=max(0.0, args.request_interval),
        max_bing_pages=max(1, args.bing_pages),
        max_bing_count=min(max(10, args.bing_count), 50),
        max_github_pages=max(1, args.github_pages),
        max_github_count=min(max(1, args.github_count), 100),
        max_github_candidates=max(0, args.github_max_candidates),
        max_cc_indexes=max(1, args.cc_indexes),
        max_cc_urls=max(1, args.cc_max_urls),
        github_token=args.github_token,
    )
    bridge = DiscoveryBridge(args.api_url, args.worker_key, timeout=args.timeout)
    selected = {value.strip().casefold() for value in args.sources.split(",") if value.strip()}
    unsupported = selected - {"seed", "bing", "github", "commoncrawl"}
    if unsupported:
        raise ValueError(f"unsupported source discovery adapters: {', '.join(sorted(unsupported))}")
    keywords = merge_unique([*all_keywords(), *args.keywords])
    adapters = []
    if "seed" in selected:
        adapters.append(SeedAdapter(args.seed, args.seed_file))
    if "bing" in selected:
        adapters.append(BingAdapter(session, timeout=args.timeout))
    if "github" in selected:
        adapters.append(GitHubAdapter(session, timeout=args.timeout))
    if "commoncrawl" in selected:
        adapters.append(CommonCrawlAdapter(session, timeout=args.timeout))
    if not adapters:
        raise ValueError("no source discovery adapters selected")
    runner = DiscoveryRunner(
        adapters,
        bridge,
        logger=logger,
        budget=budget,
        trigger=args.trigger,
        keywords=keywords,
    )
    stats = runner.run()
    logger.info("统一来源发现完成：原始 %s，归一化 %s，重复 %s，新增 %s。", stats.discovered_raw_count, stats.normalized_count, stats.duplicate_count, stats.new_candidate_count)
    print(json.dumps({
        "discovered_raw": stats.discovered_raw_count,
        "normalized": stats.normalized_count,
        "duplicates": stats.duplicate_count,
        "new_candidates": stats.new_candidate_count,
        "by_adapter": stats.adapter_stats,
        "failures": stats.failure_stats,
    }, ensure_ascii=False))


def run_dujiao_review(args: argparse.Namespace, db: StateDB) -> None:
    origin = normalize_candidate_origin(args.origin)
    if not origin:
        raise ValueError("invalid Dujiao candidate origin")
    decision = {
        "approve": "approved",
        "reject": "rejected",
        "disable": "disabled",
    }[args.decision]
    if not db.review_dujiao_candidate(origin, decision, args.note):
        raise ValueError("Dujiao candidate was not found")
    row = next(item for item in db.list_dujiao_candidates() if item["origin"] == origin)
    print(json.dumps({
        "origin": origin,
        "verification_status": row["status"],
        "review_status": row["review_status"],
        "review_note": row["review_note"],
        "reviewed_at": row["reviewed_at"],
        "published": False,
    }, ensure_ascii=False))


def intake_result_payload(result) -> tuple[str, int, str]:
    if result.matches:
        return "validated", len(result.matches), ""
    if result.is_successful_scan:
        return "no_products", 0, ""
    return "validation_failed", 0, PUBLIC_VALIDATION_FAILURE_REASONS.get(result.status, "来源验证失败")


def intake_claim_token(source_url: str) -> str | None:
    return extract_shop_token(source_url)


def run_scan(args: argparse.Namespace, db: StateDB, logger: logging.Logger) -> dict[str, Any]:
    keywords = merge_unique(args.keywords)
    limit = args.limit if args.limit > 0 else None
    intake_bridge = IntakeBridge(args.intake_api_url, args.intake_worker_key, timeout=args.timeout)
    if intake_bridge.enabled:
        try:
            claims = intake_bridge.claim(
                limit=max(1, args.intake_claim_limit),
                lease_seconds=max(60, args.intake_lease_seconds),
            )
            for claim in claims:
                source_key = str(claim.get("source_key") or "").strip()
                source_url = str(claim.get("source_url") or "").strip()
                if not source_key or not source_url:
                    logger.warning("收录申请领取结果缺少来源字段，已跳过")
                    continue
                token = intake_claim_token(source_url)
                if not token:
                    logger.warning("收录申请来源地址无法解析 token，已跳过")
                    continue
                db.upsert_intake_candidate(
                    intake_id=int(claim["intake_id"]),
                    token=token,
                    url=source_url,
                    shop_name=str(claim.get("shop_name") or ""),
                    attempt_count=int(claim.get("attempt_count") or 0),
                )
            if claims:
                logger.info("已领取 %s 家人工申请并置于优先扫描队列", len(claims))
        except (IntakeBridgeError, KeyError, TypeError, ValueError) as exc:
            logger.error("收录申请领取失败：%s", str(exc))
    policy_checker = None
    if os.getenv("LDXP_POLICY_API_URL") and os.getenv("DISCOVERY_WORKER_KEY"):
        policy_checker = ApiOriginPolicyChecker(
            os.getenv("LDXP_POLICY_API_URL", ""),
            os.getenv("DISCOVERY_WORKER_KEY", ""),
        )
    gate = CollectionPolicyGate(origin_checker=policy_checker)

    def report_intake_result(result, candidate) -> None:
        intake_id = candidate.get("intake_id")
        if not (intake_bridge.enabled and intake_id is not None):
            return
        intake_attempt = int(candidate.get("intake_attempt_count") or 0)
        intake_status, product_count, failure_reason = intake_result_payload(result)
        try:
            intake_bridge.report_result(
                intake_id=int(intake_id),
                attempt_count=intake_attempt,
                status=intake_status,
                product_count=product_count,
                failure_reason=failure_reason,
            )
        except IntakeBridgeError as exc:
            logger.error("收录申请结果回报失败：%s", str(exc))

    scheduler = DueShopScheduler(
        db,
        gate,
        scanner_factory=lambda: PublicDomScanner(
            executable_path=args.executable_path,
            timeout=args.timeout,
            page_wait=args.page_wait,
            request_interval=args.request_interval,
            logger=logger,
        ),
        logger=logger,
        batch_limit=limit or 20,
        result_callback=report_intake_result,
    )
    summary = scheduler.run_once(keywords)
    logger.info(
        "公开 DOM 扫描完成：尝试 %s，允许 %s，延期 %s，扫描 %s，命中 %s。",
        summary["attempted"],
        summary["allowed"],
        summary["deferred"],
        summary["scanned"],
        summary["matches"],
    )
    return {
        "attempted": summary["attempted"],
        "successful": summary["scanned"],
        "failed": 0,
        "blocked": 0,
        "matches": summary["matches"],
        "circuit_broken": False,
    }


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    logger = make_logger(args.verbose)
    keywords = merge_unique(args.keywords)
    db = StateDB(Path(args.db))
    try:
        if args.command == "bootstrap":
            # Ensure seed exists in DB before opening the browser.
            seed_file = Path("seeds.txt")
            discovery = Discovery(
                db,
                build_session(args.user_agent),
                timeout=args.timeout,
                max_discovered=100,
                logger=logger,
            )
            discovery.from_seeds([], seed_file)
            run_scan(args, db, logger)
            return 0

        if args.command == "discover-dujiao":
            run_dujiao_discovery(args, db, logger)
            return 0

        if args.command == "discover-sources":
            run_source_discovery(args, logger)
            return 0

        if args.command == "review-dujiao":
            run_dujiao_review(args, db)
            return 0

        if args.command in {"discover", "all"}:
            run_discovery(args, db, logger)
        if args.command in {"scan", "all"}:
            run_scan(args, db, logger)
        if args.command in {"export", "all"}:
            paths = export_results(db, args.output_dir, args.prefix)
            logger.info("Excel：%s", paths["xlsx"])
            logger.info("店铺 CSV：%s", paths["shops_csv"])
            logger.info("商品 CSV：%s", paths["products_csv"])
        return 0
    except KeyboardInterrupt:
        logger.warning("用户中断。已完成的店铺已写入 SQLite；下次可继续。")
        return 130
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
