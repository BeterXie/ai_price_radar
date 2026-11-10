import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import test from "node:test";

// A fresh process mirrors independent frontend builds: Next inlines SITE_ID.
for (const [id, domain] of Object.entries({ pricememo: "ai.pricememo.cn", aiprice: "aiprice.si", aisi: "aisi.plus", pricein: "pricein.cc", openprice: "openprice.in" })) {
  test(id + ": shared quotes, scoped publishing and canonical sitemap", () => {
    const script = [
      "import assert from 'node:assert/strict';",
      "import {createRequire} from 'node:module'; const require=createRequire(import.meta.url);",
      "const sitemap = require('./app/sitemap.ts').default;",
      "const { getProduct, getRelayStations } = require('./lib/api.ts');",
      "const { getArticle } = require('./lib/site-content.ts');",
      "const { SITE_URL } = require('./lib/site.ts');",
      "const id=process.env.NEXT_PUBLIC_SITE_ID, domain=process.env.EXPECTED_DOMAIN, calls=[];",
      "globalThis.fetch = async (url) => {",
      "  const path = new URL(String(url)).pathname; calls.push(path); let value;",
      "  if (path.endsWith('/settings')) value = {relay_hub_enabled:true};",
      "  else if (path.endsWith('/articles')) value = {items:[{slug:'our-guide',updated_at:'2026-11-10T00:00:00Z'}],total:1,page_size:100};",
      "  else if (path.endsWith('/articles/draft')) return new Response('{}',{status:404});",
      "  else if (path.endsWith('/products/chatgpt-plus')) value = {slug:'chatgpt-plus',lowest_price:'88.00',snapshot_id:42};",
      "  else if (path.endsWith('/products')) value = {items:[{slug:'chatgpt-plus',offer_count:2,brand:'OpenAI'}],total:1,snapshot_id:42};",
      "  else if (path.endsWith('/meta')) value = {source_platforms:[],relay_station_count:999,relay_hub_enabled:true};",
      "  else if (path.endsWith('/relays')) value = {items:[],total:0,enabled:true};",
      "  else if (path.endsWith('/shops')) value = [];",
      "  else if (path.endsWith('/skills')) value = {items:[],total:0};",
      "  else throw new Error('Unexpected request '+path);",
      "  return new Response(JSON.stringify(value));",
      "};",
      "const quote=await getProduct('chatgpt-plus');",
      "assert.equal(quote.snapshot_id,42); assert.equal(quote.lowest_price,'88.00');",
      "assert.equal(await getArticle('draft'),null); await getRelayStations();",
      "const urls=(await sitemap()).map(row=>row.url);",
      "assert.equal(SITE_URL,'https://'+domain);",
      "assert.ok(urls.every(url=>new URL(url).hostname===domain));",
      "assert.ok(urls.includes(SITE_URL+'/articles/our-guide'));",
      "assert.ok(calls.includes('/api/v1/products/chatgpt-plus'));",
      "assert.ok(calls.includes('/api/v1/sites/'+id+'/articles/draft'));",
      "assert.ok(calls.includes(id==='pricememo'?'/api/v1/relays':'/api/v1/sites/'+id+'/relays'));",
      "if(id!=='pricememo'){",
      "  assert.ok(!urls.some(url=>/\\/(guides|skills)(\\/|$)/.test(url)));",
      "  assert.ok(!urls.includes(SITE_URL+'/relays'));",
      "}",
    ].join("\n");
    const result = spawnSync(process.execPath, ["--import", "tsx", "--input-type=module", "-e", script], {
      cwd: new URL("..", import.meta.url), encoding: "utf8",
      env: { ...process.env, NEXT_PUBLIC_SITE_ID: id, NEXT_PUBLIC_SITE_URL: "", EXPECTED_DOMAIN: domain },
    });
    assert.equal(result.status, 0, result.stderr || result.stdout);
  });
}
