import assert from "node:assert/strict";
import test from "node:test";

import { trackButtonClick } from "../lib/analytics.ts";

test("analytics trackButtonClick silently handles network without error", async () => {
  const originalFetch = globalThis.fetch;
  const originalWindow = globalThis.window;
  let calledUrl = "";
  let calledBody = null;

  try {
    globalThis.window = { location: { pathname: "/test" } };
    globalThis.fetch = async (url, opts) => {
      calledUrl = String(url);
      calledBody = JSON.parse(opts.body);
      return { ok: true, json: async () => ({ status: "ok" }) };
    };

    await trackButtonClick("去购买", "btn_1", { extra: 123 });
    assert.match(calledUrl, /\/api\/v1\/user\/track-click/);
    assert.equal(calledBody.button_name, "去购买");
    assert.equal(calledBody.button_id, "btn_1");
    assert.equal(calledBody.extra_data.extra, 123);
  } finally {
    globalThis.fetch = originalFetch;
    globalThis.window = originalWindow;
  }
});
