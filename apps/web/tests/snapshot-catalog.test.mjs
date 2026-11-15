import assert from "node:assert/strict";
import { promises as fs } from "node:fs";
import path from "node:path";
import test from "node:test";
import { getSnapshotCatalog } from "../lib/snapshot-catalog.ts";

test("catalog loads are coalesced, versioned, bounded and retain only a short stale fallback", async (context) => {
  let now = 1_000_000;
  let version = 1;
  let malformed = false;
  let oversized = false;
  const reads = [];
  context.mock.method(Date, "now", () => now);
  context.mock.method(fs, "stat", async () => ({ size: oversized ? 1024 * 1024 : 100 }));
  context.mock.method(fs, "readFile", async (filename) => {
    reads.push(filename);
    if (malformed) return Buffer.from("{");
    if (path.basename(filename) === "latest.json") return Buffer.from(JSON.stringify({ snapshot_id: String(version) }));
    return Buffer.from(JSON.stringify({
      schema_version: "price-radar.catalog.v1", snapshot_id: version,
      snapshot_at: "2026-11-15T00:00:00Z", total: 2,
      items: [
        { slug: "unknown-price", display_name: "Unknown", lowest_price: null, data_quality_score: 80, trusted_offer_count: 2, source_count: 1 },
        { slug: "zero-price", display_name: "Zero", lowest_price: "0", data_quality_score: 80, trusted_offer_count: 2, source_count: 1 },
      ],
    }));
  });
  context.mock.method(globalThis, "fetch", () => { throw new Error("Catalog must not fetch full snapshots"); });

  const batch = await Promise.all(Array.from({ length: 100 }, () => getSnapshotCatalog()));
  assert.equal(reads.length, 2);
  assert.ok(batch.every((result) => result === batch[0]));
  assert.deepEqual(batch[0].items.map((item) => item.slug), ["zero-price", "unknown-price"]);
  assert.ok(reads.some((filename) => filename.includes(path.join("v1", "catalogs"))));

  now += 31_000;
  assert.equal((await getSnapshotCatalog()).snapshot_id, 1);
  assert.equal(reads.length, 3, "unchanged version reads only the small pointer");
  version = 2;
  now += 31_000;
  assert.equal((await getSnapshotCatalog()).snapshot_id, 2);
  assert.equal(reads.length, 5);

  malformed = true;
  now += 31_000;
  assert.equal((await getSnapshotCatalog()).snapshot_id, 2, "failed publication preserves last good data");
  now += 301_000;
  assert.equal(await getSnapshotCatalog(), null, "expired fallback allows the caller to use its API");

  malformed = false;
  oversized = true;
  now += 31_000;
  const before = reads.length;
  assert.equal(await getSnapshotCatalog(), null);
  assert.equal(reads.length, before, "oversized files are rejected before reading their body");

  oversized = false;
  now += 31_000;
  assert.equal((await getSnapshotCatalog()).snapshot_id, 2, "recovery reuses the valid version");
});
