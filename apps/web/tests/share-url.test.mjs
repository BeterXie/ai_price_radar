import assert from "node:assert/strict";
import test from "node:test";
import { buildShareUrl } from "../lib/share-url.ts";

test("shared links identify reader referrals without inheriting private query data", () => {
  const url = new URL(buildShareUrl("/skills/example?token=secret&q=person%40example.com&utm_source=old#private"));
  assert.equal(url.pathname, "/skills/example");
  assert.equal(url.hash, "");
  assert.deepEqual(Object.fromEntries(url.searchParams), {
    utm_source: "pricememo", utm_medium: "share", utm_campaign: "reader_share",
  });
});

test("comparison links are canonical and external or private destinations are rejected", () => {
  assert.equal(new URL(buildShareUrl("/compare")).pathname, "/compare");
  for (const path of ["https://other.example/compare", "//other.example/skills", "/account", "/admin", "/skills/../../account", "/compare-private"]) {
    assert.throws(() => buildShareUrl(path));
  }
});
