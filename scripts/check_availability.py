"""Check public pages and, on the production host, memory, restarts and OOMs."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import time
import urllib.request

from check_memory_budget import available_mib

URLS = (
    "https://pricememo.cn/",
    "https://pricememo.cn/shops/submit",
    "https://ai.pricememo.cn/products",
    "https://ai.pricememo.cn/health",
    "https://aiprice.si/",
    "https://aisi.plus/",
    "https://pricein.cc/",
    "https://openprice.in/",
)
CONTAINERS = (
    "ai-price-radar-api-1", "ai-price-radar-web-1", "ai-price-radar-db-1",
    "ai-price-radar-web-aiprice-1", "ai-price-radar-web-aisi-1",
    "ai-price-radar-web-pricein-1", "ai-price-radar-web-openprice-1",
)
MAX_SNAPSHOT_AGE_SECONDS = 2 * 60 * 60


def probe(url):
    started = time.monotonic()
    error = ""
    for attempt in range(2):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "PriceMemo-availability/1.0"})
            with urllib.request.urlopen(request, timeout=4) as response:
                body = response.read(2 * 1024 * 1024)
                if response.status != 200 or not body:
                    raise ValueError("Unexpected or empty HTTP response")
                if url.endswith(("/health", "/healthz")) and json.loads(body).get("status") != "ok":
                    raise ValueError("Unhealthy JSON response")
            return {"url": url, "ok": True, "seconds": round(time.monotonic() - started, 3), "retries": attempt}
        except Exception as exc:
            error = type(exc).__name__ + ": " + str(exc)
            if attempt == 0:
                time.sleep(1)
    return {"url": url, "ok": False, "seconds": round(time.monotonic() - started, 3), "error": error}


def command(args):
    return subprocess.run(args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          universal_newlines=True, timeout=10).stdout


def inspect_host(previous, now):
    memory = available_mib(Path("/proc/meminfo").read_text())
    errors = []
    if memory < 512:
        errors.append("Available memory below 512 MiB")
    items = json.loads(command(["docker", "inspect"] + list(CONTAINERS)))
    containers = {}
    old = previous.get("containers", {})
    for item in items:
        name = item["Name"].lstrip("/")
        state = item["State"]
        containers[name] = {
            "id": item["Id"], "restarts": item["RestartCount"],
            "running": state["Running"], "health": state.get("Health", {}).get("Status"),
        }
        if not state["Running"] or containers[name]["health"] == "unhealthy":
            errors.append(name + " is not healthy")
        before = old.get(name, {})
        if before.get("id") == item["Id"] and item["RestartCount"] > before.get("restarts", 0):
            errors.append(name + " restarted unexpectedly")
    since = max(float(previous.get("timestamp", now - 300)), now - 3600)
    journal = command(["journalctl", "-k", "--since", "@" + str(int(since)), "--no-pager", "-o", "cat"])
    # Pair the modern cgroup and legacy messages by victim PID. Mixed kernels
    # can emit one or both forms; counting each format then taking max loses
    # victims that appear in only one of the two formats.
    victims = set()
    for index, line in enumerate(journal.splitlines()):
        if "oom-kill:constraint=" in line:
            victim = re.search(r"\bpid=(\d+)", line)
        elif "out of memory: killed process" in line.lower():
            victim = re.search(r"killed process\s+(\d+)", line, re.IGNORECASE)
        else:
            continue
        victims.add(victim[1] if victim else ('unknown', index))
    oom_kills = len(victims)
    if oom_kills:
        errors.append("Kernel killed {} process(es) for lack of memory".format(oom_kills))
    return {"available_mib": memory, "oom_kills": oom_kills, "containers": containers}, errors


def inspect_snapshot(pointer, now):
    latest = json.loads(pointer.read_text(encoding="utf-8"))
    value = re.sub(r"([+-]\d{2}):(\d{2})$", r"\1\2", latest["published_at"].replace("Z", "+0000"))
    # The production host uses Python 3.6, which has no fromisoformat().
    for pattern in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            published = datetime.strptime(value, pattern)
            break
        except ValueError:
            continue
    else:
        raise ValueError("Invalid published snapshot timestamp")
    age = now - published.timestamp()
    errors = []
    if age < -300:
        errors.append("Published snapshot timestamp is in the future")
    elif age > MAX_SNAPSHOT_AGE_SECONDS:
        errors.append("No published snapshot for {:.0f} minutes".format(age / 60))
    return {"snapshot_id": latest["snapshot_id"], "snapshot_age_seconds": round(age)}, errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-only", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    previous = {}
    if args.output and args.output.exists():
        try:
            previous = json.loads(args.output.read_text())
        except (OSError, ValueError):
            pass
    now = time.time()
    with ThreadPoolExecutor(max_workers=4) as executor:
        pages = list(executor.map(probe, URLS))
    errors = [item["url"] + ": " + item["error"] for item in pages if not item["ok"]]
    report = {"timestamp": now, "checked_at": datetime.now(timezone.utc).isoformat(), "pages": pages}
    if not args.public_only:
        try:
            host, host_errors = inspect_host(previous, now)
            report.update(host)
            errors.extend(host_errors)
        except Exception as exc:
            errors.append("Host check failed: " + str(exc))
        try:
            pointer = Path(__file__).resolve().parents[1] / "apps/web/public/data/latest.json"
            snapshot, snapshot_errors = inspect_snapshot(pointer, now)
            report.update(snapshot)
            errors.extend(snapshot_errors)
        except Exception as exc:
            errors.append("Snapshot check failed: " + str(exc))
    report.update({"ok": not errors, "errors": errors})
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_suffix(".tmp")
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(args.output)
    print(json.dumps(report, ensure_ascii=False))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
