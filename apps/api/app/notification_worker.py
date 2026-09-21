from __future__ import annotations

import argparse
import logging
import time

from .core.config import get_settings
from .database import SessionLocal
from .services.outbox import process_once

logger = logging.getLogger(__name__)

# Upper bound for the exponential-ish backoff after consecutive loop failures.
MAX_BACKOFF_SECONDS = 300


def main() -> int:
    parser = argparse.ArgumentParser(description="Notification outbox SMTP worker")
    parser.add_argument("--once", action="store_true", help="处理一轮后退出")
    parser.add_argument("--poll-seconds", type=int, default=15, help="轮询间隔秒数")
    parser.add_argument("--batch-size", type=int, default=20, help="每轮最多发送数量")
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    get_settings()
    poll_seconds = max(1, args.poll_seconds)
    consecutive_failures = 0
    while True:
        try:
            with SessionLocal() as db:
                process_once(db, limit=max(1, args.batch_size))
        except Exception:
            # Transient failures (DB restarts, network blips) must not kill the
            # long-running worker; log, back off, and keep polling.
            consecutive_failures += 1
            logger.exception("通知队列处理失败，将在退避后重试 (连续失败 %d 次)", consecutive_failures)
            if args.once:
                return 1
            backoff = min(poll_seconds * consecutive_failures, MAX_BACKOFF_SECONDS)
            time.sleep(backoff)
            continue
        consecutive_failures = 0
        if args.once:
            return 0
        time.sleep(poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
