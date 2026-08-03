import assert from "node:assert/strict";
import test from "node:test";

import {
  buildCockpitDocument,
  convertJsonDocuments,
  parseJsonText,
} from "../lib/guides/cockpit-converter.ts";

function jwt(payload) {
  const encode = (value) => Buffer.from(JSON.stringify(value)).toString("base64url");
  return `${encode({ alg: "none", typ: "JWT" })}.${encode(payload)}.signature`;
}

const NOW = new Date("2026-08-03T08:00:00.000Z");

test("converts a ChatGPT session into Cockpit format", () => {
  const accessToken = jwt({
    exp: 1786000000,
    email: "buyer@example.com",
    "https://api.openai.com/auth": {
      chatgpt_account_id: "account-1",
      chatgpt_plan_type: "plus",
      chatgpt_user_id: "user-1",
    },
  });
  const result = convertJsonDocuments([{
    sourceName: "session.json",
    value: {
      user: { id: "user-1", email: "buyer@example.com" },
      account: { id: "account-1", planType: "plus" },
      accessToken,
      sessionToken: "session-secret",
    },
  }], NOW);

  assert.equal(result.issues.length, 0);
  assert.equal(result.accounts.length, 1);
  assert.deepEqual(result.accounts[0].account, {
    type: "codex",
    id_token: result.accounts[0].account.id_token,
    access_token: accessToken,
    refresh_token: "",
    account_id: "account-1",
    last_refresh: NOW.toISOString(),
    email: "buyer@example.com",
    expired: new Date(1786000000 * 1000).toISOString(),
  });
  assert.match(result.accounts[0].account.id_token, /\.synthetic$/);
});

test("finds nested and batched account records", () => {
  const result = convertJsonDocuments([{
    sourceName: "batch.json",
    value: {
      accounts: [
        { email: "one@example.com", account_id: "one", access_token: "token-one", id_token: "id-one" },
        { meta: { label: "two@example.com" }, tokens: { access_token: "token-two", account_id: "two", refresh_token: "refresh-two" } },
      ],
    },
  }], NOW);

  assert.equal(result.issues.length, 0);
  assert.equal(result.accounts.length, 2);
  assert.deepEqual(buildCockpitDocument(result.accounts), [
    {
      type: "codex",
      id_token: "id-one",
      access_token: "token-one",
      refresh_token: "",
      account_id: "one",
      last_refresh: NOW.toISOString(),
      email: "one@example.com",
    },
    {
      type: "codex",
      id_token: result.accounts[1].account.id_token,
      access_token: "token-two",
      refresh_token: "refresh-two",
      account_id: "two",
      last_refresh: NOW.toISOString(),
      email: "two@example.com",
    },
  ]);
});

test("reports documents without a convertible account", () => {
  const result = convertJsonDocuments([{ sourceName: "invalid.json", value: { hello: "world" } }], NOW);
  assert.equal(result.accounts.length, 0);
  assert.deepEqual(result.issues, [{
    sourceName: "invalid.json",
    path: "$",
    reason: "未找到包含 accessToken 和账号信息的对象",
  }]);
});

test("parses JSON text and reports invalid syntax", () => {
  assert.deepEqual(parseJsonText('{"ok":true}'), { ok: true });
  assert.throws(() => parseJsonText("{"), /JSON 解析失败/);
});
