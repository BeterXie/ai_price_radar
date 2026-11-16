import assert from "node:assert/strict";
import test from "node:test";
import { renderToStaticMarkup } from "react-dom/server";
import { ProductCatalogPage } from "../components/product-catalog-page.tsx";
import { JevRelayProduct } from "../components/jev-relay-product.tsx";

const station = {
  id: 1, name: "LLMPort API 中转站", url: "https://llmp.org/register?aff=existing&promo=PRICEMEMO",
  price_note: "OpenAI 0.16倍率", is_sponsored: true,
  health: { probe_model: "gpt-6.1-sol", first_token_p50_ms: 18000 },
};
const data = { enabled: true, total: 1, items: [station] };

function descendants(node) {
  if (!node || typeof node !== "object") return [];
  if (node.type?.name === "BrandCatalogFrame") return descendants(node.type(node.props));
  return [node, ...[node.props?.children].flat(Infinity).flatMap(descendants)];
}

test("JEV offers the live relay directly without crawled quote controls, empty quotes or sponsor slots", async (context) => {
  const calls = [];
  context.mock.method(globalThis, "fetch", async (url) => {
    const path = new URL(String(url)).pathname;
    calls.push(path);
    if (path.endsWith("/meta")) return Response.json({ source_platforms: [] });
    if (path.endsWith("/relays")) return Response.json(data);
    throw new Error(`Unexpected request: ${path}`);
  });
  const nodes = descendants(await ProductCatalogPage({ catalogBrand: "JEV", rawParams: {} }));
  const product = nodes.find((node) => node.type?.name === "JevRelayProduct");
  assert.ok(product);
  assert.equal(product.props.data.items[0].id, station.id);
  assert.ok(calls.includes("/api/v1/relays"));
  assert.ok(!calls.some((path) => /catalog\/groups|\/ads/.test(path)));
  assert.ok(!nodes.some((node) => ["AdSlot", "OfferScopeControls", "OfferGroupTable"].includes(node.type?.name)));
  assert.ok(!nodes.some((node) => node.props?.className === "catalog-empty"));
});

test("JEV card uses the exact LLMPort destination and supplied copy, without OpenAI metrics", () => {
  const decoys = [
    { ...station, id: 9, url: "https://notllmp.org/register" },
    { ...station, id: 10, url: "https://llmp.org.example.com/register" },
    { ...station, id: 11, url: "http://llmp.org/register" },
  ];
  const html = renderToStaticMarkup(JevRelayProduct({ data: { ...data, items: [...decoys, station] } }));
  assert.match(html, /LLMPort API 中转站/);
  assert.match(html, /JEV 官方半价，毫秒级延迟/);
  assert.match(html, /注册即送 1 美元试用额度/);
  assert.match(html, /通过 LLMPort 接入 JEV API，享官方价格 5 折/);
  assert.match(html, /https:\/\/llmp\.org\/register\?aff=existing&amp;promo=PRICEMEMO/);
  assert.match(html, /站长自营/);
  assert.doesNotMatch(html, /赞助|Sidrune|gpt-6|0\.16|18000|暂无可比报价|notllmp/);
});

test("JEV keeps disabled and missing relays hidden and gives a retry when the API fails", () => {
  for (const unavailable of [null, { ...data, enabled: false }, { ...data, items: [] }]) {
    const html = renderToStaticMarkup(JevRelayProduct({ data: unavailable }));
    assert.match(html, /role="status"/);
    assert.match(html, unavailable ? /JEV 接入暂未开放/ : /JEV 接入信息暂时无法加载/);
    assert.doesNotMatch(html, /llmp\.org|注册即送 1 美元/);
  }
});
