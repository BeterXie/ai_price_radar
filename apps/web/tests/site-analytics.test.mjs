import assert from "node:assert/strict";
import test from "node:test";

import { buildAnalyticsPath, trackBaiduPageview } from "../components/site-analytics.tsx";
import { BAIDU_PREFERENCE_KEY } from "../lib/analytics-preferences.ts";

function browser(t, hostname = "ai.pricememo.cn") {
  const scripts = [];
  const choices = new Map();
  const window = {
    location: { hostname },
    localStorage: {
      getItem: (key) => choices.get(key) ?? null,
      setItem: (key, value) => choices.set(key, value),
    },
  };
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

test("Baidu automatically records a new visitor without a saved consent choice", (t) => {
  const page = browser(t);
  trackBaiduPageview("/", "");
  assert.deepEqual(page.pageviews(), [["_trackPageview", "/"]]);
  assert.equal(page.scripts.length, 1);
});

for (const key of [BAIDU_PREFERENCE_KEY, `${BAIDU_PREFERENCE_KEY}:google`]) {
  test(`Baidu respects an existing refusal stored under ${key}`, (t) => {
    const page = browser(t);
    page.window.localStorage.setItem(key, "denied");
    trackBaiduPageview("/", "");
    trackBaiduPageview("/products", "");
    assert.equal(page.window._hmt, undefined);
    assert.deepEqual(page.scripts, []);
  });
}

test("a new explicit enable choice overrides a previous combined refusal", (t) => {
  const page = browser(t);
  page.window.localStorage.setItem(`${BAIDU_PREFERENCE_KEY}:google`, "denied");
  page.window.localStorage.setItem(BAIDU_PREFERENCE_KEY, "granted");
  trackBaiduPageview("/products", "");
  assert.deepEqual(page.pageviews(), [["_trackPageview", "/products"]]);
});

test("Google-only consent does not control Baidu tracking", (t) => {
  const page = browser(t);
  page.window.localStorage.setItem("apr:analytics-consent:v1", "denied");
  trackBaiduPageview("/", "");
  assert.equal(page.scripts.length, 1);
});

test("unreadable preferences do not bypass a saved refusal", (t) => {
  const page = browser(t);
  page.window.localStorage.getItem = () => { throw new Error("Storage blocked"); };
  trackBaiduPageview("/", "");
  assert.equal(page.window._hmt, undefined);
  assert.deepEqual(page.scripts, []);
});

test("local and preview visits cannot pollute production Baidu reports", (t) => {
  const page = browser(t, "localhost");
  trackBaiduPageview("/products", "");
  page.window.location.hostname = "preview.pricememo.cn";
  trackBaiduPageview("/products", "");
  assert.equal(page.window._hmt, undefined);
  assert.deepEqual(page.scripts, []);
});

test("Baidu loads once and counts the initial route and each distinct navigation once", (t) => {
  const page = browser(t);
  trackBaiduPageview("/products", "brand=OpenAI&page=2");
  trackBaiduPageview("/products", "page=2&brand=OpenAI");
  trackBaiduPageview("/products/chatgpt", "");
  trackBaiduPageview("/products", "brand=OpenAI&page=2");
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
    trackBaiduPageview(path, "token=secret");
  }
  assert.equal(page.window._hmt, undefined);
  assert.deepEqual(page.scripts, []);
  trackBaiduPageview("/", "");
  trackBaiduPageview("/account", "");
  trackBaiduPageview("/", "");
  assert.deepEqual(page.pageviews(), [["_trackPageview", "/"], ["_trackPageview", "/"]]);
});

test("Baidu pageviews use filtered paths without raw searches or private query parameters", (t) => {
  const page = browser(t);
  trackBaiduPageview("/products", "q=person%40example.com&token=secret&brand=OpenAI&targets=private");
  assert.deepEqual(page.pageviews(), [["_trackPageview", "/products?brand=OpenAI&q=present"]]);
});

test("public campaign labels survive page tracking while unsafe and duplicated labels do not", () => {
  assert.equal(buildAnalyticsPath("/compare", "utm_source=chatgpt.com"), "/compare?utm_source=chatgpt.com");
  assert.equal(
    buildAnalyticsPath("/compare", "utm_source=qq&utm_medium=community&utm_campaign=launch_202611&utm_content=compare_01&token=secret"),
    "/compare?utm_campaign=launch_202611&utm_content=compare_01&utm_medium=community&utm_source=qq",
  );
  for (const query of ["utm_source=person%40example.com", "utm_source=hello%20world", "utm_source=" + "a".repeat(41), "utm_source=qq&utm_source=other", "utm_term=private_search"]) {
    assert.equal(buildAnalyticsPath("/compare", query), "/compare");
  }
});

test("campaign changes do not manufacture additional pageviews", (t) => {
  const page = browser(t);
  trackBaiduPageview("/compare", "utm_source=qq&utm_medium=community");
  trackBaiduPageview("/compare", "utm_medium=community&utm_source=qq");
  trackBaiduPageview("/compare", "utm_source=wechat");
  trackBaiduPageview("/compare", "");
  trackBaiduPageview("/products/chatgpt-plus", "");
  trackBaiduPageview("/compare", "utm_source=qq");
  assert.deepEqual(page.pageviews(), [
    ["_trackPageview", "/compare?utm_medium=community&utm_source=qq"],
    ["_trackPageview", "/products/chatgpt-plus"],
    ["_trackPageview", "/compare?utm_source=qq"],
  ]);
});
