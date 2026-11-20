import assert from "node:assert/strict";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { AdSlot } from "../components/ad-slot.tsx";
import { SponsorCard } from "../components/sponsor-card.tsx";
import { SponsorShowcase } from "../components/sponsor-showcase.tsx";
import { getContextualAds } from "../lib/contextual-ads.ts";

const slot = (id, placement = "home_hero") => ({ id, placement, title: "Claude API / Claude Code", description: "Line details", sponsor_name: `Sponsor ${id}`, link_url: `https://example.com/?placement=${placement}`, image_url: "/sponsors/sidrune.svg", badge: "", cta_text: "了解 API" });

test("intake sponsor keeps referral attribution, terms and its independent placement", async (context) => {
  const item = { ...slot(20, "shop_submit"), sponsor_name: "卡密小店", title: "专业数字卡密自动交易平台", description: "新商 7 天 1% 费率。注册后联系客服领取。", link_url: "https://m.kmdian.com/register?ref=PRICEMEMORY" };
  context.mock.method(globalThis, "fetch", async (url) => {
    assert.equal(new URL(url).searchParams.get("placement"), "shop_submit");
    return Response.json({ enabled: true, items: [item] });
  });
  const html = renderToStaticMarkup(await AdSlot({ placement: "shop_submit", variant: "intake", limit: 1 }));
  assert.match(html, /data-placement="shop_submit"/);
  assert.match(html, /ref=PRICEMEMORY/);
  assert.match(html, /联系客服领取/);
  assert.match(html, /nofollow sponsored/);
  context.mock.method(globalThis, "fetch", async () => Response.json({ enabled: false, items: [] }));
  assert.equal(await AdSlot({ placement: "shop_submit", variant: "intake", limit: 1 }), null);
});

test("sponsor showcase preserves configured order and hides empty placements", async (context) => {
  context.mock.method(globalThis, "fetch", async () => Response.json({ enabled: true, items: [slot(9), slot(2), slot(6)] }));
  const html = renderToStaticMarkup(await SponsorShowcase());
  assert.deepEqual([...html.matchAll(/data-ad-id="(\d+)"/g)].map((match) => Number(match[1])), [9, 2, 6]);
  assert.equal((html.match(/sponsor-primary/g) || []).length, 1);
  assert.doesNotMatch(html, /可用率|目录前三|糖果/);
  context.mock.method(globalThis, "fetch", async () => Response.json({ enabled: false, items: [] }));
  assert.equal(await SponsorShowcase(), null);
});

test("Sidrune homepage and relay campaigns keep their configured links", async (context) => {
  const sidrune = { ...slot(2, "home_hero"), sponsor_name: "Sidrune AI" };
  const relay = { ...slot(3, "relay_hub"), sponsor_name: "Sidrune AI" };
  context.mock.method(globalThis, "fetch", async (url) => {
    const placement = new URL(url).searchParams.get("placement");
    return Response.json({ enabled: true, items: placement === "home_hero" ? [sidrune] : [relay] });
  });
  const home = renderToStaticMarkup(await SponsorShowcase());
  assert.match(home, /data-ad-id="2"/);
  assert.match(home, /placement=home_hero/);
  const relayHtml = renderToStaticMarkup(await AdSlot({ placement: "relay_hub", limit: 2, variant: "sponsor" }));
  assert.match(relayHtml, /data-ad-id="3"/);
  assert.match(relayHtml, /placement=relay_hub/);
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

test("inline and compact sponsors disclose sponsorship and preserve placement links", () => {
  const item = slot(4, "claude_detail");
  const html = renderToStaticMarkup(createElement(SponsorCard, { item, variant: "inline" }));
  assert.match(html, /赞助/);
  assert.match(html, /nofollow sponsored/);
  assert.match(html, /placement=claude_detail/);
  assert.doesNotMatch(html, /Line details|sponsor-watermark/);
  const compact = renderToStaticMarkup(createElement(SponsorCard, { item, variant: "compact" }));
  assert.match(compact, /赞助/);
  assert.match(compact, /nofollow sponsored/);
  assert.match(compact, /placement=claude_detail/);
  assert.match(compact, /Claude API \/ Claude Code|Line details/);
  assert.doesNotMatch(compact, /sponsor-watermark/);
});

test("brand toolbar and dialog use their own campaigns and retain referral links", async (context) => {
  const calls = [];
  context.mock.method(globalThis, "fetch", async (url) => {
    const placement = new URL(url).searchParams.get("placement");
    calls.push(placement);
    const item = slot(8, placement);
    if (placement.startsWith("claude_")) {
      item.sponsor_name = "Sidrune AI";
      item.title = "Claude API / Claude Code";
      item.description = "";
    } else {
      item.sponsor_name = "LLMPort";
    }
    return Response.json({ enabled: true, items: [item] });
  });
  const claude = await getContextualAds("Claude", "catalog_top");
  assert.equal(claude.feed.placement, "claude_feed");
  assert.equal(claude.detail.placement, "claude_detail");
  assert.equal(claude.toolbar.sponsor_name, "Sidrune AI");
  assert.equal(claude.feed.title, "Claude 多线路 0.25–4.5x");
  assert.match(claude.feed.description, /Claude Code · 13 条自营线路/);
  assert.match(claude.feed.description, /分组计费倍率，非官方折扣/);
  assert.equal(claude.feed.link_url, slot(8, "claude_feed").link_url);
  assert.equal(claude.detail.link_url, slot(8, "claude_detail").link_url);
  assert.deepEqual(calls.sort(), ["catalog_top", "claude_detail", "claude_feed"]);
  calls.length = 0;
  const openai = await getContextualAds("OpenAI", "product_offers");
  assert.equal(openai.feed.placement, "openai_feed");
  assert.equal(openai.toolbar.placement, "openai_feed");
  assert.equal(openai.toolbar.sponsor_name, "LLMPort");
  assert.deepEqual(calls.sort(), ["openai_detail", "openai_feed", "product_offers"]);
  calls.length = 0;
  const generic = await getContextualAds("", "catalog_top");
  assert.equal(generic.feed.placement, "catalog_top");
  assert.equal(generic.toolbar.sponsor_name, "LLMPort");
  assert.deepEqual(calls, ["catalog_top"]);
  context.mock.method(globalThis, "fetch", async () => Response.json({ enabled: false, items: [] }));
  assert.equal((await getContextualAds("", "catalog_top")).feed, undefined);
});

test("Sidrune cannot leak through generic placements to non-Claude catalogs or dialogs", async (context) => {
  const sidrune = (placement) => ({ ...slot(8, placement), sponsor_name: "Sidrune AI" });
  context.mock.method(globalThis, "fetch", async (url) => {
    const placement = new URL(url).searchParams.get("placement");
    return Response.json({ enabled: true, items: [sidrune(placement)] });
  });
  for (const brand of ["", "OpenAI", "Gemini", "Grok", "Cursor"]) {
    for (const placement of ["catalog_top", "product_offers"]) {
      const ads = await getContextualAds(brand, placement);
      assert.equal(ads.feed, undefined);
      assert.equal(ads.detail, undefined);
      assert.equal(ads.toolbar, undefined);
    }
  }
  context.mock.method(globalThis, "fetch", async (url) => {
    const placement = new URL(url).searchParams.get("placement");
    return Response.json({ enabled: true, items: [sidrune(placement), { ...slot(9, placement), sponsor_name: "LLMPort" }] });
  });
  const generic = await getContextualAds("", "catalog_top");
  assert.equal(generic.toolbar.sponsor_name, "LLMPort");
  assert.equal(generic.toolbar.id, 9);
  assert.equal(generic.feed, generic.toolbar);
});

test("Claude card additions preserve later campaign edits and disabled ad slots", async (context) => {
  const item = { ...slot(4, "claude_feed"), sponsor_name: "Sidrune AI", title: "Updated campaign", description: "Updated terms", cta_text: "Custom action" };
  context.mock.method(globalThis, "fetch", async () => Response.json({ enabled: true, items: [item] }));
  assert.deepEqual((await getContextualAds("Claude", "catalog_top")).toolbar, item);
  context.mock.method(globalThis, "fetch", async () => Response.json({ enabled: false, items: [] }));
  assert.deepEqual(await getContextualAds("Claude", "catalog_top"), { feed: undefined, detail: undefined, toolbar: undefined });
});
