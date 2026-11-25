import assert from "node:assert/strict";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { PathnameContext } from "next/dist/shared/lib/hooks-client-context.shared-runtime.js";
import { AnalyticsPageBoundary, loadClarityAnalytics } from "../components/site-analytics.tsx";

function browser(t, hostname = "ai.pricememo.cn") {
  const scripts = [];
  const window = { location: { hostname } };
  const document = {
    getElementById: (id) => scripts.find((script) => script.id === id) || null,
    createElement: (tag) => { assert.equal(tag, "script"); return {}; },
    head: { appendChild: (script) => {
      assert.deepEqual(window.clarity.q, [["consentv2", {
        analytics_Storage: "granted", ad_Storage: "denied",
      }]]);
      scripts.push(script);
    } },
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
  return { window, scripts };
}

test("Clarity loads by default only on the primary production hostname", (t) => {
  const page = browser(t);
  loadClarityAnalytics("/");
  assert.equal(page.scripts.length, 1);
  for (const hostname of ["localhost", "127.0.0.1", "preview.pricememo.cn", "pricememo.cn", "aiprice.si", "aisi.plus", "pricein.cc", "openprice.in"]) {
    page.window.location.hostname = hostname;
    loadClarityAnalytics("/");
  }
  assert.equal(page.scripts.length, 1);
});

const privatePaths = [
  null, "/account", "/account/watchlist", "/admin", "/admin/users", "/auth/callback",
  "/tools/json-to-cockpit", "/watchlist", "/shops/submit", "/shops/submit/status",
];

test("Clarity never initializes on private routes", (t) => {
  const page = browser(t);
  for (const pathname of privatePaths) loadClarityAnalytics(pathname);
  assert.equal(page.window.clarity, undefined);
  assert.deepEqual(page.scripts, []);
});

test("Clarity queues analytics settings before loading and stays a singleton across public navigation", (t) => {
  const page = browser(t);
  for (const pathname of ["/", "/", "/products", "/products/chatgpt", "/compare"]) {
    loadClarityAnalytics(pathname);
  }
  assert.equal(page.scripts.length, 1);
  assert.equal(page.scripts[0].src, "https://www.clarity.ms/tag/zj9ygr64oc");
  assert.equal(page.scripts[0].async, true);
  assert.equal(page.window.clarity.q.length, 1);
});

function renderPage(pathname) {
  return renderToStaticMarkup(createElement(PathnameContext.Provider, { value: pathname },
    createElement(AnalyticsPageBoundary, null, createElement("main", null, "page content")),
  ));
}

test("private UI cannot render in a tracked document, including a still-downloading SDK", (t) => {
  const page = browser(t);
  loadClarityAnalytics("/");
  assert.equal(page.window.clarity.v, undefined);
  for (const pathname of privatePaths) assert.equal(renderPage(pathname), "");
  assert.equal(renderPage("/products"), "<main>page content</main>");
});

test("private routes render normally in a fresh document without Clarity", (t) => {
  browser(t);
  for (const pathname of privatePaths) {
    assert.equal(renderPage(pathname), "<main>page content</main>");
  }
});
