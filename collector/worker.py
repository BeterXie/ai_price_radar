"""Durable collection worker: only private task API access, never a database URL."""
from __future__ import annotations

import gzip
import json
import logging
import errno
import os
import signal
from pathlib import Path
import subprocess
import shutil
import tempfile
import sys
import threading
import time
from datetime import datetime, timezone
from uuid import UUID

import httpx
import psutil
from price_radar_http import PinnedHTTPSClient
from price_radar_http.pacing import PacingStorageError
from collector_protocol import CONNECTORS, MAX_COMPRESSED, MAX_EXPANDED, MAX_LINE, MAX_RECORDS, SCHEMA, validate_collected_record
from connectors import get_connector
from connectors.base import SourceUnavailableError

logger = logging.getLogger("collector")
DATA = Path(os.getenv("COLLECTOR_DATA_DIR", "/data"))
API = os.environ["COLLECTOR_API_URL"].rstrip("/")
RELEASE = os.environ["COLLECTOR_RELEASE"]
WORKER = os.getenv("COLLECTOR_WORKER_ID", "oracle-1")
KEY = Path(os.environ["COLLECTOR_KEY_FILE"]).read_text().strip()
if not KEY:
    raise RuntimeError('COLLECTOR_KEY_FILE is empty')
HEADERS = {"X-Collector-Worker-Key": KEY}
KEYWORDS = json.loads((Path(__file__).parent / "collection-keywords.json").read_text(encoding="utf-8"))


class CollectionCapacityError(RuntimeError):
    pass


def terminate_tree(process):
    try:
        children = psutil.Process(process.pid).children(recursive=True)
    except psutil.NoSuchProcess:
        children = []
    for child in children:
        try:
            child.terminate()
        except psutil.NoSuchProcess:
            pass
    process.terminate()
    _, alive = psutil.wait_procs(children, timeout=5)
    for child in alive:
        try:
            child.kill()
        except psutil.NoSuchProcess:
            pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def request(path, body):
    with httpx.Client(timeout=20, follow_redirects=False, trust_env=False) as client:
        response = client.post(API + path, json=body, headers=HEADERS)
        response.raise_for_status()
        return response.json()


def heartbeat(job, stopped, lost):
    failures = 0
    while not stopped.wait(30):
        try:
            request(f"/api/v1/internal/collectors/{job['id']}/heartbeat", {"token": job["token"]})
            failures = 0
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (401, 403, 409):
                lost.set()
                return
            failures += 1
        except Exception:
            failures += 1
        if failures >= 3:
            lost.set()
            return


def run_command(args, lost, *, capture=False):
    output = tempfile.TemporaryFile(mode="w+t") if capture else None
    process = subprocess.Popen(args, stdout=output if capture else sys.stderr, stderr=sys.stderr)
    try:
        while process.poll() is None:
            if lost.wait(1):
                raise SystemExit("collector lease lost; restarting isolated worker")
        if process.returncode:
            raise RuntimeError(f"collector subprocess failed ({process.returncode})")
        if output:
            output.seek(0)
            result = output.read(1024 * 1024)
            return json.loads(result)
    finally:
        if process.poll() is None:
            terminate_tree(process)
        if output:
            output.close()


def scan(kind, lost):
    args = ["xvfb-run", "-a", sys.executable, "/app/ldxp_gpt_crawler.py", "scan",
            "--db", str(DATA / "ldxp_crawler.db"), "--rescan", "--browser-profile", str(DATA / "browser_profile"),
            "--storage-state", str(DATA / "browser_state.json"), "--limit", "25" if kind == "inventory" else "100",
            "--shop-timeout", "120", "--request-interval", "2", "--manual-challenge-seconds", "0", "--circuit-breaker", "3",
            "--keywords", *KEYWORDS]
    if kind == "inventory":
        args.append("--matched-only")
    run_command(args, lost)
    import sqlite3
    with sqlite3.connect(str(DATA / "ldxp_crawler.db")) as db:
        row = db.execute("SELECT successful,blocked,circuit_broken FROM scan_runs ORDER BY id DESC LIMIT 1").fetchone()
        if not row or row[0] == 0 or row[2]:
            raise RuntimeError("browser scan did not produce a successful collection")


def discover(lost):
    args = [sys.executable, "/app/ldxp_gpt_crawler.py", "discover-sources", "--db", str(DATA / "ldxp_crawler.db"),
            "--seed-file", "/config/general_seeds.txt", "--api-url", API,
            "--sources", "seed,16688,commoncrawl,bing,github", "--request-interval", "2",
            "--max-raw-urls", "2000", "--max-unique-candidates", "1000", "--keywords", *KEYWORDS]
    result = run_command(args, lost, capture=True)
    run_command([sys.executable, "/app/ldxp_gpt_crawler.py", "discover", "--db", str(DATA / "ldxp_crawler.db"),
                 "--seed-file", "/config/seeds.txt", "--sources", "seed,bing,commoncrawl", "--max-discovered", "500",
                 "--keywords", *KEYWORDS], lost)
    if any(result.get("failures", {}).get(key) for key in ("run_create", "batch_upsert", "run_finish")):
        raise RuntimeError("source discovery did not completely report its run")


def collect(job, lost):
    identity = str(UUID(job["id"]))
    if job["release"] != RELEASE or job["kind"] not in {"scan", "inventory", "discover"}:
        raise ValueError("unexpected collector task")
    sources = job["sources"]
    if not isinstance(sources, list) or len(sources) > 5000:
        raise ValueError("invalid source manifest")
    for spec in sources:
        if spec["connector"] not in CONNECTORS:
            raise ValueError("unsupported connector")
        if spec["connector"] != "ldxp":
            PinnedHTTPSClient.normalize_url(spec["source"])
        elif spec["source"] != "/data/ldxp_crawler.db":
            raise ValueError("invalid browser collection source")
    directory = DATA / "jobs" / identity
    directory.mkdir(parents=True, exist_ok=True)
    manifest = directory / "manifest.json"
    if manifest.exists() and json.loads(manifest.read_text()) != sources:
        raise ValueError("job manifest changed across attempts")
    if not manifest.exists():
        atomic_json(manifest, sources)
    scan_done = directory / "scan.done"
    needs_browser = any(spec["connector"] == "ldxp" for spec in sources)
    if job["kind"] == "discover":
        if not scan_done.exists():
            discover(lost)
            scan_done.touch()
    elif needs_browser and (not scan_done.exists() or time.time() - scan_done.stat().st_mtime > 3600):
        # Never let a new scan marker make an old first-source checkpoint valid.
        (directory / "0.status.json").unlink(missing_ok=True)
        scan(job["kind"], lost)
        scan_done.touch()
    total_bytes = total_count = 0
    for index, spec in enumerate(sources):
        if lost.is_set():
            raise RuntimeError("collector lease lost")
        status_path = directory / f"{index}.status.json"
        target = directory / f"{index}.jsonl"
        if status_path.exists() and target.exists() and time.time() - status_path.stat().st_mtime < 3600:
            try:
                checkpoint=json.loads(status_path.read_text())
                if checkpoint.get("status") in ("ok", "fetch_failed", "unavailable") and type(checkpoint.get("count")) is int and checkpoint.get('bytes') == target.stat().st_size:
                    total_bytes += target.stat().st_size
                    total_count += checkpoint['count']
                    if total_bytes > MAX_EXPANDED or total_count > MAX_RECORDS:
                        raise CollectionCapacityError("collection exceeds size limit")
                    continue
            except (ValueError, OSError):
                status_path.unlink(missing_ok=True)
        count, status, error = 0, "ok", ""
        temporary = target.with_suffix(".tmp")
        writing = True
        try:
            with temporary.open("w", encoding="utf-8") as out:
                writing = False
                local_source = DATA / "ldxp_crawler.db" if spec["connector"] == "ldxp" else spec["source"]
                source_bytes=0
                for record in get_connector(spec["connector"])(local_source):
                    if lost.is_set():
                        raise RuntimeError("collector lease lost")
                    record.setdefault("observed_at", record.get("collected_at") or datetime.now(timezone.utc).isoformat())
                    validate_collected_record(record, spec)
                    line = json.dumps(record, ensure_ascii=False, default=json_default) + "\n"
                    if len(line.encode()) > MAX_LINE - 64:
                        raise CollectionCapacityError("source record exceeds size limit")
                    source_bytes += len(line.encode()) + 32
                    if total_bytes + source_bytes > MAX_EXPANDED or total_count + count >= MAX_RECORDS:
                        raise CollectionCapacityError("collection exceeds size limit")
                    writing = True
                    out.write(line)
                    writing = False
                    count += 1
                writing = True
                out.flush()
                os.fsync(out.fileno())
            temporary.replace(target)
        except Exception as exc:
            if lost.is_set() or isinstance(exc, (CollectionCapacityError, PacingStorageError)) or (writing and isinstance(exc, OSError)) or (
                isinstance(exc, OSError) and exc.errno in {errno.ENOSPC, errno.EDQUOT, errno.EACCES, errno.EROFS}
            ):
                raise
            status = "unavailable" if isinstance(exc, SourceUnavailableError) else "fetch_failed"
            error = type(exc).__name__ + ": " + str(exc)[:350]
            count = 0
            target.write_text("")
            temporary.unlink(missing_ok=True)
        total_bytes += target.stat().st_size
        total_count += count
        if total_bytes > MAX_EXPANDED:
            raise ValueError("collection exceeds size limit")
        atomic_json(status_path, {"status": status, "count": count, "error": error, 'bytes':target.stat().st_size})
        logger.info("source %d/%d connector=%s status=%s records=%d", index + 1, len(sources), spec["connector"], status, count)
    bundle = directory / "result.jsonl.gz"
    with gzip.open(bundle, "wt", encoding="utf-8") as out:
        expanded = records_total = 0
        def emit(value):
            nonlocal expanded, records_total
            line=json.dumps(value, ensure_ascii=False, default=json_default) + "\n"
            expanded += len(line.encode())
            records_total += value["type"] == "record"
            if expanded > MAX_EXPANDED or records_total > MAX_RECORDS:
                raise CollectionCapacityError("collection protocol limit exceeded")
            out.write(line)
        emit({"type": "header", "schema": SCHEMA, "job_id": identity})
        for index, spec in enumerate(sources):
            emit({"type": "source", "index": index, "connector": spec["connector"], "source": spec["source"]})
            with (directory / f"{index}.jsonl").open(encoding="utf-8") as records:
                for line in records:
                    emit({"type": "record", "record": json.loads(line)})
            emit({"type": "end", **json.loads((directory / f"{index}.status.json").read_text())})
        emit({"type": "complete", "sources": len(sources)})
    if lost.is_set():
        raise RuntimeError('collector lease lost')
    if bundle.stat().st_size > MAX_COMPRESSED:
        raise CollectionCapacityError("result exceeds transport limit")
    with bundle.open("rb") as content, httpx.Client(timeout=180, trust_env=False, follow_redirects=False) as client:
        response = client.put(API + f"/api/v1/internal/collectors/{identity}/result", content=content,
                              headers={**HEADERS, "X-Collector-Lease": job["token"], "Content-Type": "application/gzip"})
        response.raise_for_status()
    logger.info("collection delivered job=%s sources=%d", identity, len(sources))
    (directory / "delivered").touch()


def cleanup_jobs(active=None):
    for old in (DATA / "jobs").glob("*"):
        marker = old / "delivered"
        age_marker=marker if marker.exists() else old / "manifest.json"
        retention=2 if marker.exists() else 7
        if old.name != active and old.is_dir() and not old.is_symlink() and age_marker.exists() and time.time()-age_marker.stat().st_mtime > retention*86400:
            shutil.rmtree(old)


def atomic_json(path, value):
    temporary=path.with_suffix(".part")
    with temporary.open('w', encoding='utf-8') as stream:
        stream.write(json.dumps(value))
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)
    if os.name == 'posix':
        descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def json_default(value):
    if hasattr(value, "as_tuple"):
        return str(value)
    raise TypeError(type(value).__name__)


def main():
    def shutdown(*_):
        raise SystemExit("collector stopping")
    signal.signal(signal.SIGTERM, shutdown)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    for name in ("INTAKE_WORKER_KEY", "DISCOVERY_WORKER_KEY"):
        path = os.getenv(name + "_FILE")
        if path:
            value = Path(path).read_text().strip()
            if not value:
                raise RuntimeError(name + '_FILE is empty')
            os.environ[name] = value
    while True:
        try:
            cleanup_jobs()
            job = request("/api/v1/internal/collectors/claim", {"worker_id": WORKER, "release": RELEASE})
            if job is None:
                time.sleep(10)
                continue
            stopped, lost = threading.Event(), threading.Event()
            keepalive = threading.Thread(target=heartbeat, args=(job, stopped, lost), daemon=True)
            keepalive.start()
            try:
                collect(job, lost)
            except Exception as exc:
                logger.warning("collection failed job=%s error=%s", job["id"], type(exc).__name__)
                if not lost.is_set():
                    request(f"/api/v1/internal/collectors/{job['id']}/failure",
                            {"token": job["token"], "error": type(exc).__name__ + ": " + str(exc)[:350],
                             'retryable': not isinstance(exc, CollectionCapacityError)})
            finally:
                stopped.set()
                keepalive.join(timeout=25)
        except Exception as exc:
            logger.warning("task API unavailable: %s", type(exc).__name__)
            time.sleep(15)


if __name__ == "__main__":
    main()
