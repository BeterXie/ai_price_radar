import assert from "node:assert/strict";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { modelsForGroup, relayGroups } from "../lib/relay-groups.ts";
import { RelayModelCatalog } from "../components/relay-model-catalog.tsx";
import { groupInputs } from "../components/relay-group-fields.tsx";

const models = [{ id: "a", name: "Model A", provider: "", description: "", context_token_limit: null, input_token_limit: null, output_token_limit: null, capabilities: [] }];

test("station group overrides are local and keep unrelated automatic groups", () => {
  const automatic = { id: "vip", name: "VIP", ratio: .5, models: null };
  const station = { model_catalog: { group_catalog: { source: "key_billing", groups: [automatic, { ...automatic, id: "free", ratio: 0 }] } }, groups: [{ ...automatic, name: "人工 VIP", ratio: .3 }] };
  const groups = relayGroups(station);
  assert.equal(groups.length, 2);
  assert.equal(groups[0].ratio, .3);
  assert.equal(groups[0].source, "站方填写");
  assert.equal(groups[1].ratio, 0);
  assert.equal(relayGroups({ ...station, groups: [] })[0].ratio, .5);
});

test("known group models control the visible list; unknown scope keeps the key list", () => {
  assert.equal(modelsForGroup(models, { models: null }), models);
  assert.deepEqual(modelsForGroup(models, { models: [] }), []);
  assert.deepEqual(modelsForGroup(models, { models: ["b", "a"] }).map((model) => model.id), ["b", "a"]);
  const catalog = { status: "ok", checked_at: "2026-10-26T00:00:00Z", synced_at: "2026-10-26T00:00:00Z", models };
  const html = renderToStaticMarkup(createElement(RelayModelCatalog, { catalog, group: { id: "g", name: "VIP", models: ["b"] } }));
  assert.match(html, /VIP · 1 个模型/);
  assert.doesNotMatch(html, /Model A/);
  assert.match(html, /模型范围来自该分组资料/);
  const unknown = renderToStaticMarkup(createElement(RelayModelCatalog, { catalog, group: { id: "g", name: "VIP", models: null } }));
  assert.match(unknown, /未提供该组的模型范围/);
  assert.match(unknown, /Model A/);
});

test("fresh group membership is not labeled as an old model list after model sync failure", () => {
  const catalog = { status: "timeout", checked_at: "2026-10-26T00:00:00Z", synced_at: "2026-10-25T00:00:00Z", models };
  const html = renderToStaticMarkup(createElement(RelayModelCatalog, { catalog, group: { id: "g", name: "VIP", models: ["new-model"] } }));
  assert.match(html, /仅影响模型详情/);
  assert.match(html, /new-model/);
  assert.doesNotMatch(html, /以下保留上次同步的清单/);
});

test("draft model text is parsed only when preparing submission", () => {
  const draft = { id: "g", name: "VIP", ratio: null, models: null, models_text: "model-a, model-b,model-a," };
  const parsed = groupInputs([draft])[0];
  assert.deepEqual(parsed.models, ["model-a", "model-b"]);
  assert.equal(draft.models_text, "model-a, model-b,model-a,");
  assert.equal("models_text" in parsed, false);
});
