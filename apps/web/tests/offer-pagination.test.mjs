import assert from "node:assert/strict";
import test from "node:test";
import { loadMoreGroups } from "../lib/offer-pagination.ts";

const group = (fingerprint) => ({ product_slug: "claude-pro", fingerprint });
const initial = { items: [group("first")], total: 50, snapshotId: 42, refreshed: false };
const endpoint = "/api/v1/catalog/groups";
const signal = () => new AbortController().signal;

test("pagination appends a page, preserving filters and the exact snapshot", async (t) => {
  t.mock.method(globalThis, "fetch", async (url) => {
    const query = new URL(url, "https://example.test").searchParams;
    assert.equal(query.get("snapshot"), "42");
    assert.equal(query.get("offset"), "1");
    assert.equal(query.get("brand"), "Claude");
    assert.equal(query.get("in_stock"), "true");
    return Response.json({ items: [group("second")], total: 48, snapshot_id: 42 });
  });
  const next = await loadMoreGroups(initial, endpoint, "brand=Claude&in_stock=true&snapshot=1&offset=90", signal());
  assert.deepEqual(next.items.map((item) => item.fingerprint), ["first", "second"]);
  assert.equal(next.total, 48);
  assert.equal(next.refreshed, false);
});

for (const stale of ["empty", "missing", "changed"]) {
  test(`a ${stale} snapshot restarts at zero and does not mix old and new quotes`, async (t) => {
    const requests = [];
    t.mock.method(globalThis, "fetch", async (url) => {
      const query = new URL(url, "https://example.test").searchParams;
      requests.push(query);
      if (query.has("snapshot")) {
        if (stale === "missing") return new Response("", { status: 404 });
        return Response.json({ items: stale === "changed" ? [group("wrong-offset")] : [], total: 0, snapshot_id: stale === "changed" ? 43 : 42 });
      }
      return Response.json({ items: [group("latest")], total: 55, snapshot_id: 43 });
    });
    const next = await loadMoreGroups(initial, endpoint, "brand=Claude&in_stock=true", signal());
    assert.equal(requests.length, 2);
    assert.equal(requests[1].get("offset"), "0");
    assert.equal(requests[1].get("in_stock"), "true");
    assert.deepEqual(next.items.map((item) => item.fingerprint), ["latest"]);
    assert.equal(next.snapshotId, 43);
    assert.equal(next.refreshed, true);
  });
}

test("repeated pages fail explicitly instead of leaving an endless scroll hint", async (t) => {
  t.mock.method(globalThis, "fetch", async () => Response.json({ items: [group("first")], total: 50, snapshot_id: 42 }));
  await assert.rejects(loadMoreGroups(initial, endpoint, "", signal()), /No new groups/);
});

test("network failure and aborted requests do not silently reset the list", async (t) => {
  let calls = 0;
  t.mock.method(globalThis, "fetch", async () => { calls++; return new Response("", { status: 503 }); });
  await assert.rejects(loadMoreGroups(initial, endpoint, "", signal()), /API 503/);
  assert.equal(calls, 1);
  const controller = new AbortController();
  controller.abort();
  t.mock.method(globalThis, "fetch", async () => { throw new DOMException("Aborted", "AbortError"); });
  await assert.rejects(loadMoreGroups(initial, endpoint, "", controller.signal), { name: "AbortError" });
});

test("a newly empty catalogue updates totals and completes the list", async (t) => {
  t.mock.method(globalThis, "fetch", async (url) => Response.json({ items: [], total: 0, snapshot_id: new URL(url, "https://example.test").searchParams.has("snapshot") ? 42 : 43 }));
  const next = await loadMoreGroups(initial, endpoint, "", signal());
  assert.equal(next.total, 0);
  assert.equal(next.items.length, 0);
});
