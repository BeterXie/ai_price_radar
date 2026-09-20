import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { buildAnalyticsPath } from "../components/google-analytics.tsx";
import { parsePage } from "../components/pagination-nav.tsx";
import { safeExternalHttpsUrl, safeInternalDemoPath } from "../lib/safe-url.ts";

test("analytics page paths keep controlled filters without leaking raw search or private parameters", () => {
  const path = buildAnalyticsPath(
    "/products",
    "q=customer%40example.com&brand=OpenAI&page=2&targets=secret&callback=https%3A%2F%2Fevil.example",
  );
  assert.equal(path, "/products?brand=OpenAI&page=2&q=present");
  assert.doesNotMatch(path, /customer|targets|callback|evil/);
});

test("directory page parsing rejects offsets beyond the public API bound", () => {
  assert.equal(parsePage("201"), 201);
  assert.equal(parsePage("202"), 1);
  assert.equal(parsePage("9007199254740991"), 1);
  assert.equal(parsePage("501", 20), 501);
  assert.equal(parsePage("502", 20), 1);
});

test("skill and coupon links accept only safe destinations", () => {
  assert.equal(safeExternalHttpsUrl("https://example.com/path"), "https://example.com/path");
  assert.equal(safeExternalHttpsUrl("javascript:alert(1)"), null);
  assert.equal(safeExternalHttpsUrl("https://user:pass@example.com"), null);
  assert.equal(safeInternalDemoPath("/demos/benchmarks/example.html"), "/demos/benchmarks/example.html");
  assert.equal(safeInternalDemoPath("/demos/../private.html"), null);
  assert.equal(safeInternalDemoPath("https://example.com/demo.html"), null);
});

test("report, demo, skill pagination, and OG routes keep their review protections", async () => {
  const [report, demo, skills, ogImage, catalog, login, coupon, markdown] = await Promise.all([
    readFile(new URL("../components/report-form.tsx", import.meta.url), "utf8"),
    readFile(new URL("../components/skills/demo-iframe.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/skills/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/products/[slug]/opengraph-image.tsx", import.meta.url), "utf8"),
    readFile(new URL("../components/product-catalog-page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../components/login-modal.tsx", import.meta.url), "utf8"),
    readFile(new URL("../components/lucky-coupon-drop.tsx", import.meta.url), "utf8"),
    readFile(new URL("../components/skills/markdown-view.tsx", import.meta.url), "utf8"),
  ]);

  assert.match(report, /maxLength=\{MAX_MESSAGE_LENGTH\}/);
  assert.match(report, /disabled=\{state === "sending"\}/);
  assert.match(report, /product_slug: productSlug/);
  assert.doesNotMatch(demo, /fetch\(src\)|srcDoc=/);
  assert.match(demo, /loading="lazy"/);
  assert.match(demo, /IntersectionObserver/);
  assert.match(skills, /<PaginationNav/);
  assert.match(skills, /name="model"/);
  assert.match(ogImage, /await getProduct\(slug/);
  assert.match(ogImage, /PRODUCT_SLUG_PATTERN/);
  assert.doesNotMatch(catalog, /:\s*"OpenAI";\s*\n\s*const productTabs/);
  assert.match(login, /requestGenerationRef/);
  assert.match(login, /code\.length !== 6/);
  assert.doesNotMatch(coupon, /role="dialog"[\s\S]{0,100}role="dialog"/);
  assert.match(coupon, /safeExternalHttpsUrl/);
  assert.match(markdown, /key="code-end"/);
});
