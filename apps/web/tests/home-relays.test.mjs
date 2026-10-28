import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { HomeRelayPreview, HomeRelays } from "../components/home-relays.tsx";

function station(id, overrides = {}) {
  return {
    id, name: `Station ${id}`, url: `https://relay-${id}.example.com`, is_sponsored: false,
    health: { status: "healthy", probe_model: "test-model", availability_7d: 98, sample_count_7d: 20, cache_sample_count_24h: 5, cache_hit_rate_24h: id },
    ...overrides,
  };
}
const render = (props) => renderToStaticMarkup(createElement(HomeRelayPreview, props));

test("homepage relay section follows the current quotes section", async () => {
  const source = await readFile(new URL("../app/page.tsx", import.meta.url), "utf8");
  const quotesIndex = source.indexOf('className="home-quotes shell"');
  const quotesEnd = source.indexOf("\n      </section>", quotesIndex);
  const relayIndex = source.indexOf("{meta?.relay_hub_enabled !== false ? (");
  assert.ok(quotesIndex >= 0, "home quotes section exists");
  assert.ok(relayIndex > quotesEnd, "relay preview appears after the quotes section");
});

test("homepage relays keep the public directory order and sponsorship disclosure", async (context) => {
  const data = { enabled: true, total: 4, items: [station(7, { is_sponsored: true }), station(2), station(9), station(1)] };
  context.mock.method(globalThis, "fetch", async () => new Response(JSON.stringify(data), { status: 200 }));
  const tree = await HomeRelays();
  const html = renderToStaticMarkup(tree);
  assert.deepEqual([...html.matchAll(/href="\/relays#relay-(\d+)"/g)].map((match) => Number(match[1])), [7, 2, 9]);
  assert.match(html, /赞助/);
  assert.match(html, /目录前三/);
  assert.match(html, /href="\/relays"/);
});

test("homepage relay preview respects disabled, empty and unavailable states", async (context) => {
  assert.equal(render({ data: { enabled: false, items: [station(1)], total: 1 } }), "");
  const empty = render({ data: { enabled: true, items: [], total: 0 } });
  assert.match(empty, /暂无已收录中转站/);
  assert.match(empty, /\/shops\/submit\?type=relay/);
  context.mock.method(globalThis, "fetch", async () => new Response("unavailable", { status: 503 }));
  const failed = renderToStaticMarkup(await HomeRelays());
  assert.match(failed, /中转站暂时无法加载/);
  assert.doesNotMatch(failed, /home-relay-card/);
});

test("homepage relay metrics distinguish zero availability and nonzero cache statistics", () => {
  const measured = station(1, { health: { status: "unhealthy", availability_7d: 0, sample_count_7d: 1, cache_hit_rate_24h: 94.92, cache_sample_count_24h: 3 } });
  const missing = station(2, { health: { availability_7d: null, sample_count_7d: 0, cache_hit_rate_24h: null, cache_sample_count_24h: 0 } });
  const insufficient = station(3, { health: { cache_hit_rate_24h: 90, cache_sample_count_24h: 2 } });
  const html = render({ data: { enabled: true, total: 3, items: [measured, missing, insufficient] } });
  assert.equal((html.match(/<dd>0%<\/dd>/g) || []).length, 1);
  assert.match(html, /<dd>94.92%<\/dd>/);
  assert.match(html, /先排除零命中/);
  assert.match(html, /<dd>暂无数据<\/dd>/);
  assert.match(html, /<dd>样本不足<\/dd>/);
  assert.doesNotMatch(html, /<dd>90%<\/dd>/);
  assert.match(html, /接口异常/);
});
