import test from "node:test";
import assert from "node:assert/strict";

import { normalizePublicHttpsUrl, validatePolicyRequest } from "../lib/source-policy.ts";

test("policy url normalization accepts public https and rejects unsafe input", () => {
  assert.equal(normalizePublicHttpsUrl("pay.ldxp.cn/shop/TEST01"), "https://pay.ldxp.cn/shop/TEST01");
  assert.equal(normalizePublicHttpsUrl("http://shop.example.com/x"), "https://shop.example.com/x");
  assert.equal(normalizePublicHttpsUrl("https://shop.example.com:443/x"), "https://shop.example.com/x");
  assert.equal(normalizePublicHttpsUrl("https://user:pass@shop.example.com"), null);
  assert.equal(normalizePublicHttpsUrl("https://127.0.0.1"), null);
  assert.equal(normalizePublicHttpsUrl("https://shop.local"), null);
  assert.equal(normalizePublicHttpsUrl(""), null);
});

test("policy request validation requires url and email", () => {
  assert.equal(
    validatePolicyRequest({
      source_url: "https://pay.ldxp.cn/shop/TEST01",
      request_type: "opt_out",
      requester_email: "owner@example.com",
      reason: "please remove",
    }),
    null,
  );
  assert.ok(
    validatePolicyRequest({
      source_url: "not a url",
      request_type: "opt_out",
      requester_email: "owner@example.com",
      reason: "",
    }),
  );
  assert.ok(
    validatePolicyRequest({
      source_url: "https://pay.ldxp.cn/shop/TEST01",
      request_type: "opt_out",
      requester_email: "bad",
      reason: "",
    }),
  );
});
