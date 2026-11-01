import assert from "node:assert/strict";
import test from "node:test";
import ComparePage from "../app/compare/page.tsx";

function descendants(node) {
  if (!node || typeof node !== "object") return [];
  return [node, ...[node.props?.children].flat(Infinity).flatMap(descendants)];
}

test("comparison prices and linked details use the same monthly recharge scope", async (context) => {
  let request;
  context.mock.method(globalThis, "fetch", async (url) => {
    request = new URL(String(url));
    return new Response(JSON.stringify({ snapshot_at: null, items: [{ slug: "claude-pro", brand: "Claude", display_name: "Claude Pro", offer_count: 2, trusted_offer_count: 2, lowest_price: "132.99", price_currency: "CNY", in_stock_count: 2, source_count: 2, last_updated_at: null }] }), { status: 200 });
  });
  const page = await (ComparePage.default || ComparePage)();
  assert.equal(request.searchParams.get("comparable"), "true");
  const link = descendants(page).find((node) => node.props?.href?.startsWith("/products/claude-pro"));
  assert.ok(link);
  const detail = new URL(link.props.href, "https://example.test");
  for (const [name, value] of Object.entries({ delivery_type: "subscription_recharge", period: "one_month" })) {
    assert.equal(request.searchParams.get(name), value);
    assert.equal(detail.searchParams.get(name), value);
  }
});
