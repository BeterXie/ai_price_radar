import assert from "node:assert/strict";
import test from "node:test";

import { trackBaiduPageview } from "../components/site-analytics.tsx";

function browser(t, hostname = "ai.pricememo.cn") {
  const scripts = [];
  const window = { location: { hostname } };
  const document = {
    getElementById: (id) => scripts.find((script) => script.id === id) || null,
    createElement: (tag) => {
      assert.equal(tag, "script");
      return {};
    },
    head: {
      appendChild: (script) => {
        // Initial configuration and the first PV must be queued before the SDK can execute.
        assert.deepEqual(window._hmt[0], ["_setAutoPageview", false]);
        assert.equal(window._hmt[1][0], "_trackPageview");
        scripts.push(script);
      },
    },
  };
  const originalWindow = globalThis.window;
  const originalDocument = globalThis.document;
  globalThis.window = window;
  globalThis.document = document;
  t.after(() => {
    if (originalWindow === undefined) delete globalThis.window;
    else globalThis.window = originalWindow;
    if (originalDocument === undefined) delete globalThis.document;
    else globalThis.document = originalDocument;
  });
  return { window, scripts, pageviews: () => (window._hmt || []).filter(([command]) => command === "_trackPageview") };
}

test("Baidu does not load or queue data before consent", (t) => {
  const page = browser(t);
  trackBaiduPageview("/", "", false);
  assert.equal(page.window._hmt, undefined);
  assert.deepEqual(page.scripts, []);
});

test("local and preview visits cannot pollute production Baidu reports", (t) => {
  const page = browser(t, "localhost");
  trackBaiduPageview("/products", "", true);
  page.window.location.hostname = "preview.pricememo.cn";
  trackBaiduPageview("/products", "", true);
  assert.equal(page.window._hmt, undefined);
  assert.deepEqual(page.scripts, []);
});

test("Baidu loads once and counts the initial route and each distinct navigation once", (t) => {
  const page = browser(t);
  trackBaiduPageview("/products", "brand=OpenAI&page=2", true);
  trackBaiduPageview("/products", "page=2&brand=OpenAI", true);
  trackBaiduPageview("/products/chatgpt", "", true);
  trackBaiduPageview("/products", "brand=OpenAI&page=2", true);
  assert.deepEqual(page.pageviews(), [
    ["_trackPageview", "/products?brand=OpenAI&page=2"],
    ["_trackPageview", "/products/chatgpt"],
    ["_trackPageview", "/products?brand=OpenAI&page=2"],
  ]);
  assert.equal(page.scripts.length, 1);
  assert.equal(page.scripts[0].src, "https://hm.baidu.com/hm.js?0abf0f3c54963dc5874f6a4ebcbfaf37");
  assert.equal(page.scripts[0].async, true);
});

test("private routes never load the SDK or queue a pageview", (t) => {
  const page = browser(t);
  for (const path of [null, "/account", "/account/watchlist", "/admin", "/admin/users", "/auth/callback", "/tools/json-to-cockpit"]) {
    trackBaiduPageview(path, "token=secret", true);
  }
  assert.equal(page.window._hmt, undefined);
  assert.deepEqual(page.scripts, []);
  trackBaiduPageview("/", "", true);
  trackBaiduPageview("/account", "", true);
  trackBaiduPageview("/", "", true);
  assert.deepEqual(page.pageviews(), [["_trackPageview", "/"], ["_trackPageview", "/"]]);
});

test("Baidu pageviews use filtered paths without raw searches or private query parameters", (t) => {
  const page = browser(t);
  trackBaiduPageview("/products", "q=person%40example.com&token=secret&brand=OpenAI&targets=private", true);
  assert.deepEqual(page.pageviews(), [["_trackPageview", "/products?brand=OpenAI&q=present"]]);
});
