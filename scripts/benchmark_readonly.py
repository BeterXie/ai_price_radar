from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time

import httpx


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    index = min(len(values) - 1, round((len(values) - 1) * fraction))
    return sorted(values)[index]


async def run_stage(client: httpx.AsyncClient, url: str, concurrency: int, total: int) -> dict[str, float | int]:
    semaphore = asyncio.Semaphore(concurrency)

    async def request_once() -> tuple[float, int, int]:
        async with semaphore:
            started = time.perf_counter()
            try:
                response = await client.get(url)
                return time.perf_counter() - started, response.status_code, len(response.content)
            except httpx.HTTPError:
                return time.perf_counter() - started, 0, 0

    started = time.perf_counter()
    results = await asyncio.gather(*(request_once() for _ in range(total)))
    elapsed = time.perf_counter() - started
    durations = [item[0] for item in results]
    errors = sum(status < 200 or status >= 400 for _, status, _ in results)
    sizes = [size for _, status, size in results if 200 <= status < 400]
    return {
        "concurrency": concurrency,
        "requests": total,
        "errors": errors,
        "rps": round(total / elapsed, 2),
        "p50_ms": round(percentile(durations, 0.50) * 1000, 1),
        "p95_ms": round(percentile(durations, 0.95) * 1000, 1),
        "p99_ms": round(percentile(durations, 0.99) * 1000, 1),
        "mean_bytes": round(statistics.mean(sizes)) if sizes else 0,
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="Bounded read-only HTTP concurrency benchmark")
    parser.add_argument("url")
    parser.add_argument("--concurrency", default="1,5,10,20,40")
    parser.add_argument("--requests-per-worker", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=15)
    args = parser.parse_args()
    levels = [int(value) for value in args.concurrency.split(",")]
    limits = httpx.Limits(max_connections=max(levels), max_keepalive_connections=max(levels))
    async with httpx.AsyncClient(timeout=args.timeout, limits=limits, follow_redirects=True) as client:
        for _ in range(3):
            await client.get(args.url)
        for concurrency in levels:
            total = max(20, concurrency * args.requests_per_worker)
            result = await run_stage(client, args.url, concurrency, total)
            print(json.dumps(result, ensure_ascii=False), flush=True)
            if result["errors"] or result["p95_ms"] > args.timeout * 900:
                break


if __name__ == "__main__":
    asyncio.run(main())
