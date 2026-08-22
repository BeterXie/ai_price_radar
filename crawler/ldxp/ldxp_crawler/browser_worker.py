from __future__ import annotations

import logging
import multiprocessing
import os
import signal
from multiprocessing.connection import Connection
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

from .browser_scanner import BrowserShopScanner
from .models import ShopScanResult


PROFILE_SINGLETONS = ("SingletonLock", "SingletonSocket", "SingletonCookie")
WorkerTarget = Callable[[dict[str, Any], Connection, bool], None]


def _worker_logger(verbose: bool) -> logging.Logger:
    logger = logging.getLogger(f"ldxp-browser-worker-{os.getpid()}")
    logger.handlers.clear()
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", "%H:%M:%S"))
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.propagate = False
    return logger


def _browser_worker_main(config: dict[str, Any], connection: Connection, verbose: bool) -> None:
    if hasattr(os, "setsid"):
        os.setsid()
    logger = _worker_logger(verbose)
    try:
        with BrowserShopScanner(logger=logger, **config) as scanner:
            connection.send(("ready", 0, ""))
            while True:
                message = connection.recv()
                if not message or message[0] == "stop":
                    return
                _, job_id, candidate, keywords = message
                result = scanner.scan_shop(candidate, keywords)
                connection.send(("result", job_id, result))
    except (EOFError, BrokenPipeError):
        return
    except BaseException as exc:
        try:
            connection.send(("fatal", 0, f"{type(exc).__name__}: {exc}"))
        except (EOFError, BrokenPipeError, OSError):
            pass
    finally:
        connection.close()


class BrowserScanSupervisor:
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
        shop_timeout: float,
        logger: logging.Logger,
        verbose: bool = False,
        startup_timeout: float = 45.0,
        shutdown_timeout: float = 5.0,
        _worker_target: WorkerTarget = _browser_worker_main,
    ):
        self.profile_dir = profile_dir
        self.shop_timeout = max(0.05, float(shop_timeout))
        self.startup_timeout = max(0.05, float(startup_timeout))
        self.shutdown_timeout = max(0.05, float(shutdown_timeout))
        self.logger = logger
        self.verbose = verbose
        self.worker_target = _worker_target
        self.config = {
            "profile_dir": profile_dir,
            "storage_state_path": storage_state_path,
            "executable_path": executable_path,
            "headless": headless,
            "timeout": timeout,
            "page_wait": page_wait,
            "manual_challenge_seconds": manual_challenge_seconds,
            "max_pages": max_pages,
            "page_size": page_size,
            "fetch_mode": fetch_mode,
            "request_interval": request_interval,
        }
        self.context = multiprocessing.get_context("spawn")
        self.process: Any = None
        self.connection: Optional[Connection] = None
        self.job_id = 0

    def __enter__(self) -> "BrowserScanSupervisor":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()

    def scan_shop(self, candidate: Any, keywords: Sequence[str]) -> ShopScanResult:
        token = str(candidate["token"])
        try:
            self._ensure_worker()
            assert self.connection is not None
            self.job_id += 1
            job_id = self.job_id
            self.connection.send(("scan", job_id, dict(candidate), list(keywords)))
            if not self.connection.poll(self.shop_timeout):
                self.logger.error(
                    "店铺 %s 扫描超过 %.0f 秒硬时限；终止并重启浏览器 Worker。",
                    token,
                    self.shop_timeout,
                )
                self._stop_worker(force=True)
                return ShopScanResult(
                    token=token,
                    status="network_error",
                    shop_url=str(candidate["url"]),
                    error=f"单店扫描超过 {self.shop_timeout:.0f} 秒硬时限，浏览器 Worker 已重启",
                    engine="browser",
                )
            message_type, result_job_id, payload = self.connection.recv()
            if message_type != "result" or result_job_id != job_id or not isinstance(payload, ShopScanResult):
                raise RuntimeError(f"浏览器 Worker 返回异常：{message_type}: {payload}")
            return payload
        except (EOFError, BrokenPipeError, OSError, RuntimeError) as exc:
            self._stop_worker(force=True)
            return ShopScanResult(
                token=token,
                status="network_error",
                shop_url=str(candidate["url"]),
                error=f"浏览器 Worker 异常退出：{type(exc).__name__}: {exc}",
                engine="browser",
            )

    def close(self) -> None:
        self._stop_worker(force=False)

    def _ensure_worker(self) -> None:
        if self.process is not None and self.process.is_alive() and self.connection is not None:
            return
        self._stop_worker(force=True)
        self._cleanup_profile_singletons()
        parent_connection, child_connection = self.context.Pipe(duplex=True)
        process = self.context.Process(
            target=self.worker_target,
            args=(self.config, child_connection, self.verbose),
            name="ldxp-browser-worker",
        )
        process.start()
        child_connection.close()
        self.process = process
        self.connection = parent_connection
        if not parent_connection.poll(self.startup_timeout):
            self._stop_worker(force=True)
            raise RuntimeError(f"浏览器 Worker 启动超过 {self.startup_timeout:.0f} 秒")
        message_type, _, payload = parent_connection.recv()
        if message_type != "ready":
            self._stop_worker(force=True)
            raise RuntimeError(f"浏览器 Worker 启动失败：{payload}")

    def _stop_worker(self, *, force: bool) -> None:
        process = self.process
        connection = self.connection
        if process is None:
            if connection is not None:
                connection.close()
            self.connection = None
            return
        if process.is_alive() and not force and connection is not None:
            try:
                connection.send(("stop",))
            except (EOFError, BrokenPipeError, OSError):
                pass
            process.join(self.shutdown_timeout)
        if process.is_alive():
            self._terminate_process_tree(process)
        process.join(self.shutdown_timeout)
        if connection is not None:
            connection.close()
        self.process = None
        self.connection = None
        try:
            self._cleanup_profile_singletons()
        except RuntimeError as exc:
            self.logger.error("清理浏览器单例文件失败：%s", exc)

    def _terminate_process_tree(self, process: Any) -> None:
        terminated_group = False
        if os.name != "nt" and process.pid:
            try:
                process_group = os.getpgid(process.pid)
                if process_group == process.pid:
                    os.killpg(process_group, signal.SIGTERM)
                    terminated_group = True
            except (ProcessLookupError, PermissionError):
                pass
        if not terminated_group:
            process.terminate()
        process.join(2.0)
        if not process.is_alive():
            return
        if os.name != "nt" and process.pid:
            try:
                process_group = os.getpgid(process.pid)
                if process_group == process.pid:
                    os.killpg(process_group, signal.SIGKILL)
                    return
            except (ProcessLookupError, PermissionError):
                pass
        process.kill()

    def _cleanup_profile_singletons(self) -> None:
        for name in PROFILE_SINGLETONS:
            path = self.profile_dir / name
            if path.is_symlink():
                path.unlink()
            elif path.exists():
                raise RuntimeError(f"拒绝删除非符号链接浏览器单例文件：{path}")
