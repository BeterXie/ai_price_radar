import assert from "node:assert/strict";
import test from "node:test";
import { generateMetadata } from "../app/brands/[slug]/page.tsx";
import ProductsPage from "../app/products/page.tsx";

test("only a populated, unfiltered brand URL is indexable and variants keep its canonical", async (context) => {
  let offerCount = 3;
  context.mock.method(globalThis, "fetch", async () => new Response(JSON.stringify({ items: [], offer_count: offerCount }), { status: 200 }));
  const props = { params: Promise.resolve({ slug: "claude" }), searchParams: Promise.resolve({}) };
  const canonical = "https://ai.pricememo.cn/brands/claude";
  const clean = await generateMetadata(props);
  assert.equal(clean.robots.index, true);
  assert.equal(clean.alternates.canonical, canonical);
  assert.match(clean.title, /Claude 比价/);
  for (const filters of [{ q: "Max" }, { in_stock: "true" }, { brand: "OpenAI" }, { source_platform: "16688" }]) {
    const filtered = await generateMetadata({ ...props, searchParams: Promise.resolve(filters) });
    assert.equal(filtered.robots.index, false);
    assert.equal(filtered.alternates.canonical, canonical);
  }
  offerCount = 0;
  assert.equal((await generateMetadata(props)).robots.index, false);
  const missing = await generateMetadata({ ...props, params: Promise.resolve({ slug: "unknown" }) });
  assert.equal(missing.robots.index, false);
});

test("legacy brand and platform links permanently redirect while retaining search filters", async () => {
  const page = ProductsPage.default || ProductsPage;
  for (const name of ["brand", "platform"]) {
    await assert.rejects(() => page({ searchParams: Promise.resolve({ [name]: "Claude", q: "Max", in_stock: "true", comparable: "false" }) }), (error) => {
      assert.match(error.digest, /NEXT_REDIRECT/);
      assert.match(error.digest, /\/brands\/claude\?q=Max&in_stock=true&comparable=false;308;/);
      return true;
    });
  }
});
