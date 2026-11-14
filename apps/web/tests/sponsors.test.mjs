import assert from "node:assert/strict";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { SponsorCard } from "../components/sponsor-card.tsx";
import { SponsorShowcase } from "../components/sponsor-showcase.tsx";
import { getContextualAds } from "../lib/contextual-ads.ts";

const slot = (id, placement = "home_hero") => ({ id, placement, title: "Claude API / Claude Code", description: "Line details", sponsor_name: `Sponsor ${id}`, link_url: `https://example.com/?placement=${placement}`, image_url: "/sponsors/sidrune.svg", badge: "", cta_text: "了解 API" });

test("sponsor showcase preserves configured order and hides empty placements", async (context) => {
  context.mock.method(globalThis, "fetch", async () => Response.json({ enabled: true, items: [slot(9), slot(2), slot(6)] }));
  const html = renderToStaticMarkup(await SponsorShowcase());
  assert.deepEqual([...html.matchAll(/data-ad-id="(\d+)"/g)].map((match) => Number(match[1])), [9, 2, 6]);
  assert.equal((html.match(/sponsor-primary/g) || []).length, 1);
  assert.doesNotMatch(html, /可用率|目录前三|糖果/);
  context.mock.method(globalThis, "fetch", async () => Response.json({ enabled: false, items: [] }));
  assert.equal(await SponsorShowcase(), null);
});

test("contextual slots separate Claude and OpenAI targeting and preserve placement URLs", async (context) => {
  const calls = [];
  context.mock.method(globalThis, "fetch", async (url) => {
    const placement = new URL(url).searchParams.get("placement");
    calls.push(placement);
    return Response.json({ enabled: true, items: [slot(placement.endsWith("_feed") ? 4 : 5, placement)] });
  });
  for (const brand of ["", "Google", "ChatGPT"]) assert.deepEqual(await getContextualAds(brand), {});
  assert.equal(calls.length, 0);
  const ads = await getContextualAds("Claude");
  assert.deepEqual(calls.sort(), ["claude_detail", "claude_feed"]);
  assert.equal(ads.feed.id, 4);
  assert.equal(ads.detail.id, 5);
  assert.notEqual(ads.feed.link_url, ads.detail.link_url);
  calls.length = 0;
  const openai = await getContextualAds("OpenAI");
  assert.deepEqual(calls.sort(), ["openai_detail", "openai_feed"]);
  assert.equal(openai.detail.placement, "openai_detail");
  assert.notEqual(openai.feed.link_url, ads.feed.link_url);
  context.mock.method(globalThis, "fetch", async () => Response.json({ enabled: false, items: [] }));
  assert.deepEqual(await getContextualAds("OpenAI"), { feed: undefined, detail: undefined });
});

test("compact sponsor always discloses sponsorship and omits the full creative", () => {
  const item = slot(4, "claude_detail");
  const html = renderToStaticMarkup(createElement(SponsorCard, { item, variant: "inline" }));
  assert.match(html, /赞助/);
  assert.match(html, /nofollow sponsored/);
  assert.match(html, /placement=claude_detail/);
  assert.doesNotMatch(html, /Line details|sponsor-watermark/);
});
