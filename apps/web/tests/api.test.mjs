import assert from "node:assert/strict";
import test from "node:test";

import { ApiError, getProduct, getShop } from "../lib/api.ts";

test("API resource helpers only treat 404 as missing", async () => {
  const originalFetch = globalThis.fetch;
  try {
    globalThis.fetch = async () => ({ ok: false, status: 404, json: async () => ({}) });
    assert.equal(await getProduct("missing"), null);
    assert.equal(await getShop("missing"), null);

    globalThis.fetch = async () => ({ ok: false, status: 503, json: async () => ({}) });
    await assert.rejects(() => getProduct("unavailable"), (error) => error instanceof ApiError && error.status === 503);
    await assert.rejects(() => getShop("unavailable"), (error) => error instanceof ApiError && error.status === 503);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
