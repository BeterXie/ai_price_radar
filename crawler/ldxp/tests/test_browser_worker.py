from __future__ import annotations

import logging
import time

from ldxp_crawler.browser_worker import BrowserScanSupervisor
from ldxp_crawler.models import ShopScanResult


def fake_browser_worker(_config, connection, _verbose):
    connection.send(("ready", 0, ""))
    while True:
        message = connection.recv()
        if message[0] == "stop":
            return
        _, job_id, candidate, _keywords = message
        if candidate["token"] == "HANG":
            time.sleep(30)
            continue
        connection.send((
            "result",
            job_id,
            ShopScanResult(token=candidate["token"], status="success"),
        ))


def test_hung_shop_is_killed_and_next_shop_uses_fresh_worker(tmp_path):
    supervisor = BrowserScanSupervisor(
        profile_dir=tmp_path / "profile",
        storage_state_path=tmp_path / "state.json",
        executable_path=None,
        headless=True,
        timeout=5,
        page_wait=0,
        manual_challenge_seconds=0,
        max_pages=1,
        page_size=10,
        fetch_mode="all",
        request_interval=0,
        shop_timeout=0.2,
        startup_timeout=5,
        shutdown_timeout=0.2,
        logger=logging.getLogger("browser-worker-test"),
        _worker_target=fake_browser_worker,
    )

    with supervisor:
        timed_out = supervisor.scan_shop(
            {"token": "HANG", "url": "https://pay.ldxp.cn/shop/HANG"},
            ["gpt"],
        )
        recovered = supervisor.scan_shop(
            {"token": "OK", "url": "https://pay.ldxp.cn/shop/OK"},
            ["gpt"],
        )

    assert timed_out.status == "network_error"
    assert "硬时限" in timed_out.error
    assert recovered.status == "success"
