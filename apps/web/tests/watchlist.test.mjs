import assert from "node:assert/strict";
import test from "node:test";

import { MAX_WATCHLIST_ITEMS, normalizeWatchThreshold, readWatchlist, WATCHLIST_KEY } from "../components/watch-button.tsx";
import { isValidPublicSourceUrl } from "../lib/source-intake.mjs";

test("watchlist thresholds are finite positive decimals", () => {
  assert.equal(normalizeWatchThreshold(""), "");
  assert.equal(normalizeWatchThreshold("12.50"), "12.50");
  assert.equal(normalizeWatchThreshold("1..2"), null);
  assert.equal(normalizeWatchThreshold("0"), null);
  assert.equal(normalizeWatchThreshold("Infinity"), null);
});

test("public source URL validation rejects private IPv4-mapped IPv6", () => {
  assert.equal(isValidPublicSourceUrl("https://[::ffff:192.168.1.1]/feed.json"), false);
  assert.equal(isValidPublicSourceUrl("https://[::ffff:10.0.0.1]/feed.json"), false);
  assert.equal(isValidPublicSourceUrl("https://[::ffff:8.8.8.8]/feed.json"), true);
});

test("corrupt watchlist entries are rejected and the feed contract is capped", () => {
  const values = Array.from({ length: MAX_WATCHLIST_ITEMS + 2 }, (_, index) => ({
    slug: `product-${index}`,
    name: `Product ${index}`,
    threshold: index === 1 ? "1..2" : "10.00",
    added_at: new Date(0).toISOString(),
  }));
  const store = new Map([[WATCHLIST_KEY, JSON.stringify(values)]]);
  const originalWindow = globalThis.window;
  globalThis.window = {
    localStorage: {
      getItem: (key) => store.get(key) || null,
      setItem: (key, value) => store.set(key, value),
    },
  };
  try {
    const items = readWatchlist();
    assert.equal(items.length, MAX_WATCHLIST_ITEMS);
    assert.equal(items.some((item) => item.slug === "product-1"), false);
  } finally {
    globalThis.window = originalWindow;
  }
});
