import assert from "node:assert/strict";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { RelayHealthPanel } from "../components/relay-health.tsx";

test("benchmark renders zero distinctly from unknown and shows both denominators", () => {
  const health = {
    cache_hit_rate_24h: 0, cache_sample_count_24h: 2, cache_attempt_count_24h: 3,
    candy_pass_rate_24h: 0, candy_sample_count_24h: 2, candy_passed_count_24h: 0,
    candy_inconclusive_count_24h: 1, candy_verdict: "failed", candy_answer: "29",
  };
  const render = (value) => renderToStaticMarkup(createElement(RelayHealthPanel, { health: value, now: 0 }));
  const html = render(health);
  assert.match(html, /糖果测试通过率/);
  assert.match(html, /重复输入缓存率/);
  assert.match(html, /糖果：0\/2 次通过 · 1 次无法判定；缓存：2\/3 次用量完整/);
  assert.match(html, /最近：未通过（29）/);
  assert.equal((html.match(/<dd>0%<\/dd>/g) || []).length, 2);
  assert.doesNotMatch(render({ ...health, cache_hit_rate_24h: null, candy_pass_rate_24h: null }), /<dd>0%<\/dd>/);
});
