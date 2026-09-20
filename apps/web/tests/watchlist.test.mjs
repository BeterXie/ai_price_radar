import assert from "node:assert/strict";
import test from "node:test";

import {
  ANONYMOUS_WATCHLIST_KEY,
  MAX_WATCHLIST_ITEMS,
  normalizeWatchThreshold,
  readAnonymousWatchlist,
  readUserWatchlist,
  readWatchlist,
  userWatchlistKey,
  WATCHLIST_KEY,
  writeAnonymousWatchlist,
  writeUserWatchlist,
} from "../components/watch-button.tsx";
import { isValidPublicSourceUrl } from "../lib/source-intake.mjs";

function withFakeWindow(store, run) {
  const originalWindow = globalThis.window;
  globalThis.window = {
    localStorage: {
      getItem: (key) => store.get(key) || null,
      setItem: (key, value) => store.set(key, value),
      removeItem: (key) => store.delete(key),
      get length() {
        return store.size;
      },
      key: (index) => Array.from(store.keys())[index] ?? null,
    },
    dispatchEvent: () => true,
  };
  try {
    return run();
  } finally {
    globalThis.window = originalWindow;
  }
}

test("watchlist thresholds are finite positive decimals", () => {
  assert.equal(normalizeWatchThreshold(""), "");
  assert.equal(normalizeWatchThreshold("12.50"), "12.50");
  assert.equal(normalizeWatchThreshold("1..2"), null);
  assert.equal(normalizeWatchThreshold("0"), null);
  assert.equal(normalizeWatchThreshold("Infinity"), null);
  assert.equal(normalizeWatchThreshold("99999999.99"), "99999999.99");
  assert.equal(normalizeWatchThreshold("100000000.00"), null);
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
  withFakeWindow(store, () => {
    const items = readWatchlist();
    assert.equal(items.length, MAX_WATCHLIST_ITEMS);
    assert.equal(items.some((item) => item.slug === "product-1"), false);
  });
});

test("per-account watchlists are isolated from each other and from anonymous data", () => {
  const store = new Map();
  withFakeWindow(store, () => {
    const item = (slug) => ({
      slug,
      name: slug,
      threshold: "10.00",
      added_at: new Date(0).toISOString(),
    });

    writeUserWatchlist(1, [item("for-user-1")]);
    writeUserWatchlist(2, [item("for-user-2")]);
    writeAnonymousWatchlist([item("anonymous")]);

    assert.deepEqual(readUserWatchlist(1).map((i) => i.slug), ["for-user-1"]);
    assert.deepEqual(readUserWatchlist(2).map((i) => i.slug), ["for-user-2"]);
    assert.deepEqual(readAnonymousWatchlist().map((i) => i.slug), ["anonymous"]);

    // Account data must never bleed into the anonymous migration source.
    assert.equal(readAnonymousWatchlist().some((i) => i.slug === "for-user-1"), false);
    assert.ok(store.has(userWatchlistKey(1)));
    assert.ok(store.has(ANONYMOUS_WATCHLIST_KEY));
  });
});

test("legacy shared key is absorbed once into the anonymous list", () => {
  const legacyItem = {
    slug: "legacy-product",
    name: "Legacy",
    threshold: "5.00",
    added_at: new Date(0).toISOString(),
  };
  const store = new Map([[WATCHLIST_KEY, JSON.stringify([legacyItem])]]);
  withFakeWindow(store, () => {
    const first = readAnonymousWatchlist();
    assert.deepEqual(first.map((i) => i.slug), ["legacy-product"]);
    // The legacy key is consumed, so a different account cannot inherit it.
    assert.equal(store.has(WATCHLIST_KEY), false);
  });
});
