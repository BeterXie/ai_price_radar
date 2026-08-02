import assert from "node:assert/strict";
import test from "node:test";

import { isValidPublicSourceUrl, SOURCE_INTAKE_COPY, SOURCE_INTAKE_OPTIONS } from "../lib/source-intake.mjs";

test("source intake defaults to auto and exposes source-specific examples", () => {
  assert.equal(SOURCE_INTAKE_OPTIONS[0]?.id, "auto");
  assert.match(SOURCE_INTAKE_COPY.auto.hint, /商品页面或公开 Feed/);
  assert.match(SOURCE_INTAKE_COPY.ldxp.placeholder, /pay\.ldxp\.cn\/shop/);
  assert.match(SOURCE_INTAKE_COPY.dujiao_next.hint, /店铺根地址/);
  assert.match(SOURCE_INTAKE_COPY.merchant_json.placeholder, /ai-price-radar\.json/);
});

test("client validation accepts a public HTTPS URL regardless of declared type", () => {
  assert.equal(isValidPublicSourceUrl("https://shop.example.com"), true);
  assert.equal(isValidPublicSourceUrl("https://pay.ldxp.cn/shop/example"), true);
  assert.equal(isValidPublicSourceUrl("http://shop.example.com"), false);
  assert.equal(isValidPublicSourceUrl("https://localhost/feed.json"), false);
});
