import test from "node:test";
import assert from "node:assert/strict";
import { alertView, alertMoney, alertTime, parseAlertReport, currentAlertRows, nextAlertExpiry } from "../lib/alert-report.ts";
import { currentReport, readBoundedJson } from "../lib/alert-report-server.ts";

const row = { offer_id: 1, product_name: "Team 5x", shop_name: "店铺", product_slug: "chatgpt-business", price: "18.00", currency: "CNY", observed_at: "2026-11-21T06:00:00Z", ends_at: "2026-11-21T07:00:00Z", is_head_car: false };
const report = { schema_version: "price-radar.alerts.v1", snapshot_id: 1, published_at: "2026-11-21T06:05:00Z", stale_offer_hours: 72, drops: [], rises: [], team: [row] };

test("Team rows disappear at their actual deadline and stale quotes do not remain actionable", () => {
  assert.equal(currentAlertRows(report, "team", Date.parse("2026-11-21T06:59:59Z")).length, 1);
  assert.equal(currentAlertRows(report, "team", Date.parse(row.ends_at)).length, 0);
  const dropReport = { ...report, drops: [{ ...row, old_price: "20", diff: "-2", percent_change: -10 }] };
  assert.equal(currentAlertRows(dropReport, "drops", Date.parse("2026-11-25T06:00:00Z")).length, 0);
});

test("invalid reports fail rather than silently looking like no changes", () => {
  assert.equal(parseAlertReport(report).snapshot_id, 1);
  assert.throws(() => parseAlertReport({ ...report, team: [{ ...row, price: "NaN" }] }));
  assert.throws(() => parseAlertReport({ ...report, team: [{ ...row, ends_at: "bad" }] }));
  assert.throws(() => parseAlertReport({ ...report, drops: [{ ...row }] }));
});

test("links select a current board and use explicit Beijing time and currency", () => {
  assert.equal(alertView("team"), "team");
  assert.equal(alertView("rises"), "rises");
  assert.equal(alertView("unknown"), "drops");
  assert.equal(alertMoney("18", "USD"), "$18.00");
  assert.match(alertTime(row.ends_at), /15:00/);
});

test("old report is rejected as soon as the public pointer advances", () => {
  assert.equal(currentReport(report, { snapshot_id: "1" }).snapshot_id, 1);
  assert.throws(() => currentReport(report, { snapshot_id: "2" }), /pending/);
  assert.throws(() => currentReport(report, { snapshot_id: [1] }), /pending/);
});

test("bad decimal strings cannot turn missing values into zero-price claims", () => {
  for (const change of [{ old_price: "", diff: "-2" }, { old_price: "20", diff: null }, { old_price: "20", diff: "" }]) {
    assert.throws(() => parseAlertReport({ ...report, drops: [{ ...row, percent_change: -10, ...change }] }));
  }
  for (const patch of [{ published_at: 2026 }, { published_at: "2026-11-21T06:00:00" }, { stale_offer_hours: 1e308 }]) {
    assert.throws(() => parseAlertReport({ ...report, ...patch }));
  }
  assert.throws(() => parseAlertReport({ ...report, team: [{ ...row, is_head_car: "false" }] }));
});

test("next clock tick matches the earliest deadline and row/count expire together", () => {
  const before = Date.parse(row.ends_at) - 900;
  const tick = nextAlertExpiry(report, before);
  assert.equal(tick, Date.parse(row.ends_at));
  assert.equal(currentAlertRows(report, "team", tick).length, 0);
});

test("API fallback bounds chunked responses even without Content-Length", async () => {
  let cancelled = false;
  const body = new ReadableStream({
    start(controller) { controller.enqueue(new Uint8Array(20)); },
    cancel() { cancelled = true; },
  });
  await assert.rejects(readBoundedJson(new Response(body), 10), /too large/);
  assert.equal(cancelled, true);
  assert.deepEqual(await readBoundedJson(new Response('{"ok":true}'), 100), { ok: true });
});
