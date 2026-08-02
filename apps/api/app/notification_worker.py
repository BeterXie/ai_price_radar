from __future__ import annotations

import argparse
import logging
import time

from .core.config import get_settings
from .database import SessionLocal
from .services.outbox import process_once


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
    while True:
        with SessionLocal() as db:
            process_once(db, limit=max(1, args.batch_size))
        if args.once:
            return 0
        time.sleep(max(1, args.poll_seconds))


if __name__ == "__main__":
    raise SystemExit(main())
