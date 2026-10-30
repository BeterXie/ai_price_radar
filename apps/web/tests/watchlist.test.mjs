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
  watchItemsToMigrate,
  writeAnonymousWatchlist,
  writeUserWatchlist,
} from "../components/watch-button.tsx";
import { isValidPublicSourceUrl } from "../lib/source-intake.mjs";
import { fetchUserSubscriptions, saveUserSubscription, updateUserSubscription, deleteUserSubscription } from "../lib/auth-client.ts";

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

function watchItem(slug, threshold = "10.00") {
  return { slug, name: slug, threshold, added_at: new Date(0).toISOString() };
}

test("legacy Pro slugs in every browser cache resolve to canonical products", () => {
  const legacy = [watchItem("chatgpt-pro-5x", "25.00"), watchItem("chatgpt-pro-20x", "45.00")];
  for (const key of [WATCHLIST_KEY, ANONYMOUS_WATCHLIST_KEY, userWatchlistKey(7)]) {
    withFakeWindow(new Map([[key, JSON.stringify(legacy)]]), () => {
      const items = key === userWatchlistKey(7) ? readUserWatchlist(7) : readAnonymousWatchlist();
      assert.deepEqual(items.map(({ slug, threshold }) => [slug, threshold]), [
        ["chatgpt-pro-100", "25.00"], ["chatgpt-pro-200", "45.00"],
      ]);
    });
  }
});

test("canonical local configuration wins over an alias regardless of entry order", () => {
  const legacy = watchItem("chatgpt-pro-5x", "5.00");
  const canonical = watchItem("chatgpt-pro-100", "30.00");
  for (const values of [[legacy, canonical], [canonical, legacy]]) {
    const store = new Map([[ANONYMOUS_WATCHLIST_KEY, JSON.stringify(values)]]);
    withFakeWindow(store, () => {
      assert.equal(readAnonymousWatchlist().length, 1);
      assert.equal(readAnonymousWatchlist()[0].threshold, "30.00");
      assert.ok(writeAnonymousWatchlist(values));
      assert.ok(writeUserWatchlist(7, values));
      for (const key of [ANONYMOUS_WATCHLIST_KEY, userWatchlistKey(7)]) {
        const persisted = JSON.parse(store.get(key));
        assert.equal(persisted.length, 1);
        assert.equal(persisted[0].slug, "chatgpt-pro-100");
        assert.equal(persisted[0].threshold, "30.00");
      }
    });
  }
});

test("subscription API normalizes aliases while keeping canonical thresholds and channels", async (context) => {
  const legacy = { id: 1, product_slug: "chatgpt-pro-5x", target_price: "5.00", notify_email: true, notify_bot: true };
  const canonical = { id: 2, product_slug: "chatgpt-pro-100", target_price: "50.00", notify_email: false, notify_bot: false };
  let cloud = [legacy, canonical];
  const requests = [];
  context.mock.method(globalThis, "fetch", async (url, options) => {
    requests.push({ url: String(url), options });
    return new Response(JSON.stringify({ items: cloud, count: cloud.length, email_bound: true, bot_bound: true }), { status: 200 });
  });
  for (const items of [[legacy, canonical], [canonical, legacy]]) {
    cloud = items;
    const result = await fetchUserSubscriptions();
    assert.deepEqual(result.items, [canonical]);
    assert.equal(result.count, 1);
  }
  cloud = [{ ...legacy, product_slug: "chatgpt-pro-20x" }];
  assert.equal((await fetchUserSubscriptions()).items[0].product_slug, "chatgpt-pro-200");

  const settings = { target_price: "60.00", notify_email: false, notify_bot: true };
  await saveUserSubscription({ product_slug: "chatgpt-pro-5x", ...settings });
  assert.deepEqual(JSON.parse(requests.at(-1).options.body), { product_slug: "chatgpt-pro-100", ...settings });
  await updateUserSubscription("chatgpt-pro-20x", { notify_bot: false });
  assert.ok(requests.at(-1).url.endsWith("/subscriptions/chatgpt-pro-200"));
  assert.equal(requests.at(-1).options.method, "PATCH");
  assert.deepEqual(JSON.parse(requests.at(-1).options.body), { notify_bot: false });
  await deleteUserSubscription("chatgpt-pro-5x");
  assert.ok(requests.at(-1).url.endsWith("/subscriptions/chatgpt-pro-100"));
  assert.equal(requests.at(-1).options.method, "DELETE");
});

test("login migration skips matching cloud aliases and preserves cloud settings", () => {
  for (const cloudSlug of ["chatgpt-pro-100", "chatgpt-pro-5x"]) {
    const cloud = [{ product_slug: cloudSlug, target_price: "80.00", notify_email: false, notify_bot: false }];
    const before = structuredClone(cloud);
    const local = [watchItem("chatgpt-pro-5x", "10.00"), watchItem("chatgpt-pro-100", "20.00"), watchItem("chatgpt-pro-20x", "40.00")];
    const pending = watchItemsToMigrate(local, cloud);
    assert.deepEqual(pending.map(({ slug, threshold }) => [slug, threshold]), [["chatgpt-pro-200", "40.00"]]);
    assert.deepEqual(cloud, before);
  }
});
