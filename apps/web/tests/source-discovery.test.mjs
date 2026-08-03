import test from "node:test";
import assert from "node:assert/strict";

import {
  candidateQuery,
  candidateStatusLabel,
  funnelFromRuns,
  runStatusLabel,
} from "../lib/source-discovery.ts";

test("candidate status labels cover the full queue lifecycle", () => {
  assert.equal(candidateStatusLabel("promoted"), "已促进");
  assert.equal(candidateStatusLabel("needs_re_review"), "需复审");
  assert.equal(candidateStatusLabel("unknown-future"), "unknown-future");
  assert.equal(runStatusLabel("partial"), "部分失败");
});

test("funnel aggregates discovery run metrics", () => {
  const funnel = funnelFromRuns([
    {
      discovered_raw_count: 10,
      normalized_count: 8,
      duplicate_count: 2,
      new_candidate_count: 6,
      detected_count: 4,
      ai_matched_count: 3,
      auto_approved_count: 2,
      pending_review_count: 1,
      validation_failed_count: 1,
      promoted_intake_count: 2,
    },
    {
      discovered_raw_count: 5,
      normalized_count: 4,
      duplicate_count: 1,
      new_candidate_count: 3,
      detected_count: 2,
      ai_matched_count: 1,
      auto_approved_count: 0,
      pending_review_count: 1,
      validation_failed_count: 1,
      promoted_intake_count: 0,
    },
  ]);
  assert.deepEqual(funnel, {
    discovered_raw: 15,
    normalized: 12,
    duplicates: 3,
    new_candidates: 9,
    detected: 6,
    ai_matched: 4,
    auto_approved: 2,
    pending_review: 2,
    validation_failed: 2,
    promoted: 2,
  });
});

test("candidate query builder only includes active filters", () => {
  assert.equal(candidateQuery({}), "");
  assert.equal(
    candidateQuery({ status: "promoted", detected_platform: "woocommerce", ai_hit: true, limit: 50 }),
    "?status=promoted&detected_platform=woocommerce&ai_hit=true&limit=50",
  );
  assert.equal(candidateQuery({ discovered_by: "bing" }), "?discovered_by=bing");
});
