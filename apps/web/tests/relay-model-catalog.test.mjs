import assert from "node:assert/strict";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { RelayModelCatalog } from "../components/relay-model-catalog.tsx";

const catalog = {
  status: "ok", checked_at: "2026-10-25T17:00:00Z", synced_at: "2026-10-25T17:00:00Z", truncated: false,
  models: [{ id: "model-1", name: "Model One", description: "<script>untrusted()</script>", provider: "Example", context_token_limit: 10000, input_token_limit: null, output_token_limit: 500, capabilities: [] }],
};

test("model catalog displays returned metadata and labels the key-scoped list", () => {
  const html = renderToStaticMarkup(createElement(RelayModelCatalog, { catalog }));
  assert.match(html, /接口返回 1 个模型/);
  assert.match(html, /Model One/);
  assert.match(html, /model-1/);
  assert.match(html, /上下文 10,000 tokens/);
  assert.doesNotMatch(html, /输入上限/);
  assert.match(html, /具体模型能否调用/);
  assert.match(html, /搜索该站模型/);
  assert.doesNotMatch(html, /<script>/);
});

test("failed sync retains previous models and timestamp without claiming freshness", () => {
  const html = renderToStaticMarkup(createElement(RelayModelCatalog, { catalog: { ...catalog, status: "timeout" } }));
  assert.match(html, /最近同步超时/);
  assert.match(html, /上次同步的清单/);
  assert.match(html, /Model One/);
  assert.match(html, /2026-10-25T17:00:00Z/);
});

test("empty successful catalog is distinct from a sync that has never succeeded", () => {
  const html = renderToStaticMarkup(createElement(RelayModelCatalog, { catalog: { ...catalog, models: [] } }));
  assert.match(html, /该密钥的模型清单为空/);
  const never = renderToStaticMarkup(createElement(RelayModelCatalog, { catalog: { ...catalog, synced_at: null, models: [], status: "unsupported" } }));
  assert.match(never, /站点暂未提供模型列表接口/);
  assert.doesNotMatch(never, /该密钥的模型清单为空/);
});
