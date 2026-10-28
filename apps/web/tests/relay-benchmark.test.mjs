import assert from "node:assert/strict";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { RelayHealthPanel } from "../components/relay-health.tsx";

test("benchmark labels nonzero cache samples and preserves a zero candy score", () => {
  const health = {
    cache_hit_rate_24h: 94.92, cache_sample_count_24h: 3, cache_attempt_count_24h: 5,
    candy_pass_rate_24h: 0, candy_sample_count_24h: 2, candy_passed_count_24h: 0,
    candy_inconclusive_count_24h: 1, candy_verdict: "failed", candy_answer: "29",
  };
  const render = (value) => renderToStaticMarkup(createElement(RelayHealthPanel, { health: value, now: 0 }));
  const html = render(health);
  assert.match(html, /糖果测试通过率/);
  assert.match(html, /重复输入缓存率/);
  assert.match(html, /糖果：0\/2 次通过 · 1 次无法判定；缓存：3\/5 次非零样本 · 去极值后 1 次均值/);
  assert.match(html, /先排除零命中/);
  assert.match(html, /<dd>94.92%<\/dd>/);
  assert.match(html, /最近：未通过（29）/);
  assert.equal((html.match(/<dd>0%<\/dd>/g) || []).length, 1);
  assert.doesNotMatch(render({ ...health, cache_hit_rate_24h: null, candy_pass_rate_24h: null }), /<dd>0%<\/dd>/);
});

test("cache rate distinguishes insufficient samples from no data", () => {
  for (const count of [0, 1, 2]) {
    const html = renderToStaticMarkup(createElement(RelayHealthPanel, {
      health: { cache_hit_rate_24h: null, cache_sample_count_24h: count, cache_attempt_count_24h: count + 4 }, now: 0,
    }));
    assert.match(html, /满 3 个非零样本后计算/);
    assert.match(html, count ? /<dd>样本不足<\/dd>/ : /<dd>暂无数据<\/dd>/);
    assert.doesNotMatch(html, /<dd>0%<\/dd>/);
  }
});
