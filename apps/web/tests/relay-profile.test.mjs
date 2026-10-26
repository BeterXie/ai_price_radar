import assert from "node:assert/strict";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { RelayProfileFields, EMPTY_RELAY_PROFILE, relayProfileInputs, relayProfileError } from "../components/relay-profile-fields.tsx";

const draft = {
  ...EMPTY_RELAY_PROFILE,
  tagline: " 统一接入 ", description: " 接入说明\n余额与退款规则 ",
  price_note: " 官方价 0.7 折起 ", billing_note: " 按量计费 ",
};

test("relay profile parses pasted lists without losing input or silently truncating", () => {
  const input = { ...draft, supported_models_text: " model-a，model-b\nmodel-a; model-c； ", tags_text: "支持支付宝, 余额不过期，支持支付宝" };
  assert.deepEqual(relayProfileInputs(input), {
    tagline: "统一接入", description: "接入说明\n余额与退款规则", price_note: "官方价 0.7 折起", billing_note: "按量计费",
    supported_models: ["model-a", "model-b", "model-c"], tags: ["支持支付宝", "余额不过期"],
  });
  assert.equal(input.supported_models_text, " model-a，model-b\nmodel-a; model-c； ");
  const manyModels = { ...draft, supported_models_text: Array.from({ length: 41 }, (_, n) => `model-${n}`).join(",") };
  assert.equal(relayProfileInputs(manyModels).supported_models.length, 41);
  assert.match(relayProfileError(manyModels), /40/);
  assert.match(relayProfileError({ ...draft, tags_text: Array.from({ length: 13 }, (_, n) => `标签${n}`).join(",") }), /12/);
  assert.match(relayProfileError({ ...draft, supported_models_text: "m".repeat(61) }), /60/);
  assert.match(relayProfileError({ ...draft, tags_text: "t".repeat(31) }), /30/);
});

test("required profile cannot be blank; model discovery and tags remain optional", () => {
  assert.equal(relayProfileError(draft), "");
  for (const field of ["tagline", "description", "price_note", "billing_note"]) {
    assert.match(relayProfileError({ ...draft, [field]: " \n " }), /请填写/);
  }
  const html = renderToStaticMarkup(createElement(RelayProfileFields, { value: draft, onChange() {} }));
  for (const id of ["relay-tagline", "relay-description", "relay-price-note", "relay-billing-note"]) {
    assert.match(html, new RegExp(`id="${id}" required=""`));
  }
  assert.match(html, /审核上线后会使用检测密钥自动同步可用模型/);
  assert.doesNotMatch(html, /赞助|排序/);
});
