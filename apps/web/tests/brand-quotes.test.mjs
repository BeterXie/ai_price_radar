import assert from "node:assert/strict";
import test from "node:test";
import { spawnSync } from "node:child_process";
import { quoteInventory, quoteProductHref } from "../lib/brand-quotes.ts";

test("quote inventory distinguishes unavailable, unknown and numeric stock", () => {
  assert.equal(quoteInventory({ stock_status: "out_of_stock", stock_count: 0 }), "缺货");
  assert.equal(quoteInventory({ stock_status: "in_stock", stock_count: null }), "有货 · 数量未提供");
  assert.equal(quoteInventory({ stock_status: "in_stock", stock_count: 7 }), "有货 · 7");
  assert.equal(quoteInventory({ stock_status: "unknown", stock_count: null }), "库存未知");
});

test("product navigation preserves offer filters without carrying pagination or another product", () => {
  const href = quoteProductHref("claude-pro", "brand=OpenAI&product=chatgpt-plus&offset=60&snapshot=8610&limit=30&delivery_type=account&in_stock=true&comparable=true");
  const url = new URL(href, "https://aisi.plus");
  assert.equal(url.pathname, "/products/claude-pro");
  assert.deepEqual([...url.searchParams], [["delivery_type", "account"], ["in_stock", "true"]]);
  assert.equal(new URL(quoteProductHref("claude-pro", ""), "https://aisi.plus").searchParams.get("comparable"), "false");
});

for (const site of ["aiprice", "aisi", "pricein", "openprice"]) {
  test(`${site}: the visible price and inventory belong to the linked seller`, () => {
    const script = `
      import React from 'react';
      import {renderToStaticMarkup} from 'react-dom/server';
      import {createRequire} from 'node:module';
      const require=createRequire(import.meta.url);
      const {BrandQuotes}=require('./components/brand-quotes.tsx');
      const offer={id:5,shop_name:'Visible merchant',shop_token:'merchant',original_name:'Monthly plan',delivery_type:'subscription_recharge',service_period:'one_month',price:'88.00',currency:'CNY',stock_status:'in_stock',stock_count:3,is_comparable:true,is_trusted_price:true,source_url:'https://example.com/item-5',source_platform_label:'Public source',observed_at:'2026-11-11T00:00:00Z'};
      const group={product_slug:'claude-pro',product_name:'Claude Pro',fingerprint:'sample',representative:offer,shop_count:2,offer_count:2,lowest_price:'66.00',in_stock_count:999};
      process.stdout.write(renderToStaticMarkup(React.createElement(BrandQuotes,{groups:[group],footer:null})));
    `;
    const result=spawnSync(process.execPath,["--import","tsx","--input-type=module","-e",script],{cwd:new URL("..",import.meta.url),encoding:"utf8",env:{...process.env,NEXT_PUBLIC_SITE_ID:site}});
    assert.equal(result.status,0,result.stderr);
    assert.match(result.stdout,/88\.00/);
    assert.match(result.stdout,/有货 · 3/);
    assert.match(result.stdout,/https:\/\/example.com\/item-5/);
    assert.match(result.stdout,/Visible merchant/);
    assert.match(result.stdout,/官方直充 \/ 代充/);
    assert.doesNotMatch(result.stdout,/66\.00|有货 · 999|<details/);
  });
}
