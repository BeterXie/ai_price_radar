import assert from "node:assert/strict";
import test from "node:test";

import { getSearchEngineVerificationMetadata } from "../lib/search-engine-verification.ts";

test("search-engine verification metadata is omitted without configured tokens", () => {
  assert.equal(getSearchEngineVerificationMetadata({}), undefined);
});

test("search-engine verification metadata maps Bing and Baidu tokens", () => {
  assert.deepEqual(
    getSearchEngineVerificationMetadata({
      BING_SITE_VERIFICATION: "  bing-token  ",
      BAIDU_SITE_VERIFICATION: "baidu-token",
    }),
    {
      other: {
        "msvalidate.01": "bing-token",
        "baidu-site-verification": "baidu-token",
      },
    },
  );
});

test("blank verification values are ignored", () => {
  assert.equal(
    getSearchEngineVerificationMetadata({
      BING_SITE_VERIFICATION: " ",
      BAIDU_SITE_VERIFICATION: "\t",
    }),
    undefined,
  );
});
