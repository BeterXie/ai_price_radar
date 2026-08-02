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
from ldxp_crawler.exporter import export_results
from ldxp_crawler.intake_bridge import IntakeBridge, IntakeBridgeError
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
    candidates = db.list_candidates(
        rescan=args.rescan,
        retry_blocked=args.retry_blocked,
        retry_failed=not args.no_retry_failed,
        matched_only=args.matched_only,
        limit=limit,
    )
    config = {
        "headless": args.headless,
        "executable_path": str(args.executable_path) if args.executable_path else "",
        "profile": str(args.browser_profile),
        "storage_state": str(args.storage_state),
        "max_pages": args.max_pages,
        "page_size": args.page_size,
        "fetch_mode": args.fetch_mode,
        "request_interval": args.request_interval,
        "matched_only": args.matched_only,
        "circuit_breaker": args.circuit_breaker,
    }
    run_id = db.start_run(args.command, keywords, "browser", config)
    attempted = successful = failed = blocked = match_count = 0
    consecutive_blocks = 0
    circuit_broken = False
    note = ""

    if not candidates:
        note = "没有符合重试条件的候选店铺"
        db.finish_run(
            run_id,
            attempted=0,
            successful=0,
            failed=0,
            blocked=0,
            matches=0,
            circuit_broken=False,
            note=note,
        )
        logger.info(note)
        return {"attempted": 0, "successful": 0, "failed": 0, "blocked": 0, "matches": 0}

    logger.info(
        "准备扫描 %s 家；关键词=%s；模式=%s。首次运行如出现验证，请在浏览器窗口正常完成。",
        len(candidates), "、".join(keywords), "无头" if args.headless else "有头",
    )

    try:
        with BrowserShopScanner(
            profile_dir=args.browser_profile,
            storage_state_path=args.storage_state,
            executable_path=args.executable_path,
            headless=args.headless,
            timeout=args.timeout,
            page_wait=args.page_wait,
            manual_challenge_seconds=args.manual_challenge_seconds,
            max_pages=args.max_pages,
            page_size=args.page_size,
            fetch_mode=args.fetch_mode,
            request_interval=args.request_interval,
            logger=logger,
        ) as scanner:
            for index, candidate in enumerate(candidates, start=1):
                result = scanner.scan_shop(candidate, keywords)
                attempted += 1
                db.save_scan_result(result, run_id)
                intake_id = candidate["intake_id"]
                if intake_bridge.enabled and intake_id is not None:
                    intake_attempt = int(candidate["intake_attempt_count"] or 0)
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
                if result.is_successful_scan:
                    successful += 1
                    match_count += len(result.matches)
                    consecutive_blocks = 0
                    logger.info(
                        "[%s/%s] %s | %s | 商品=%s 命中=%s%s",
                        index, len(candidates), result.token, result.status,
                        result.scanned_item_count, len(result.matches),
                        f" | {result.error}" if result.error else "",
                    )
                else:
                    failed += 1
                    if result.status in BLOCK_STATUSES:
                        blocked += 1
                        consecutive_blocks += 1
                    else:
                        consecutive_blocks = 0
                    logger.warning(
                        "[%s/%s] %s | %s | %s",
                        index, len(candidates), result.token, result.status, result.error,
                    )

                if args.circuit_breaker > 0 and consecutive_blocks >= args.circuit_breaker:
                    circuit_broken = True
                    note = (
                        f"连续 {consecutive_blocks} 家出现站点级阻断/验证/限流，已熔断；"
                        "剩余候选保持原状态，未继续请求。"
                    )
                    logger.error(note)
                    break
    except Exception as exc:
        failed += 1
        note = f"浏览器初始化或扫描器异常：{type(exc).__name__}: {exc}"
        logger.error(note)
        if "Executable doesn't exist" in str(exc) or "browserType.launch" in str(exc):
            logger.error("请先执行：python -m playwright install chromium")
    finally:
        db.finish_run(
            run_id,
            attempted=attempted,
            successful=successful,
            failed=failed,
            blocked=blocked,
            matches=match_count,
            circuit_broken=circuit_broken,
            note=note,
        )

    return {
        "attempted": attempted,
        "successful": successful,
        "failed": failed,
        "blocked": blocked,
        "matches": match_count,
        "circuit_broken": circuit_broken,
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
