import assert from "node:assert/strict";
import test from "node:test";

import { isValidPublicSourceUrl, SOURCE_INTAKE_COPY, SOURCE_INTAKE_OPTIONS } from "../lib/source-intake.mjs";

test("source intake exposes four categories and identifies independent stores automatically", () => {
  assert.deepEqual(SOURCE_INTAKE_OPTIONS.map(({ id, label }) => [id, label]), [
    ["ldxp", "链动小铺"], ["16688", "16688"], ["independent", "独立站点"], ["relay", "API 中转站"],
  ]);
  assert.match(SOURCE_INTAKE_COPY.ldxp.placeholder, /pay\.ldxp\.cn\/shop/);
  assert.match(SOURCE_INTAKE_COPY["16688"].placeholder, /16688\.com\.cn\/shop\/HARVEY/);
  assert.match(SOURCE_INTAKE_COPY.independent.hint, /自动识别 Dujiao-Next/);
  assert.match(SOURCE_INTAKE_COPY.independent.hint, /JSON Feed/);
  assert.match(SOURCE_INTAKE_COPY.relay.hint, /Base URL/);
});

test("client validation accepts a public HTTPS URL regardless of declared type", () => {
  assert.equal(isValidPublicSourceUrl("https://shop.example.com"), true);
  assert.equal(isValidPublicSourceUrl("https://pay.ldxp.cn/shop/example"), true);
  assert.equal(isValidPublicSourceUrl("https://wzyp.cn/shop/KFLA"), true);
  assert.equal(isValidPublicSourceUrl("http://shop.example.com"), false);
  assert.equal(isValidPublicSourceUrl("https://localhost/feed.json"), false);
});
