import assert from "node:assert/strict";
import test from "node:test";

import {
  buildCockpitDocument,
  COCKPIT_LIMITS,
  convertJsonDocuments,
  convertJsonTexts,
  parseJsonText,
} from "../lib/guides/cockpit-converter.ts";

function jwt(payload) {
  const encode = (value) => Buffer.from(JSON.stringify(value)).toString("base64url");
  return `${encode({ alg: "none", typ: "JWT" })}.${encode(payload)}.signature`;
}

function opaqueToken(seed = "opaque") {
  return `${seed}-${"x".repeat(60)}`;
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
        { email: "one@example.com", account_id: "one", access_token: opaqueToken("one"), id_token: "id-one" },
        { meta: { label: "two@example.com" }, tokens: { access_token: opaqueToken("two"), account_id: "two", refresh_token: "refresh-two" } },
      ],
    },
  }], NOW);

  assert.equal(result.issues.length, 0);
  assert.equal(result.accounts.length, 2);
  assert.deepEqual(buildCockpitDocument(result.accounts), [
    {
      type: "codex",
      id_token: "id-one",
      access_token: opaqueToken("one"),
      refresh_token: "",
      account_id: "one",
      last_refresh: NOW.toISOString(),
      email: "one@example.com",
      expired: "",
    },
    {
      type: "codex",
      id_token: result.accounts[1].account.id_token,
      access_token: opaqueToken("two"),
      refresh_token: "refresh-two",
      account_id: "two",
      last_refresh: NOW.toISOString(),
      email: "two@example.com",
      expired: "",
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

test("rejects an account that only has email and a short access token", () => {
  const result = convertJsonDocuments([{
    sourceName: "incomplete.json",
    value: { email: "buyer@example.com", access_token: "opaque-token" },
  }], NOW);

  assert.equal(result.accounts.length, 0);
  assert.equal(result.issues.length, 1);
  assert.match(result.issues[0].reason, /accessToken 长度不足/);
  assert.match(result.issues[0].reason, /account_id/);
});

test("rejects a long opaque access token without an account id", () => {
  const result = convertJsonDocuments([{
    sourceName: "no-account-id.json",
    value: { email: "buyer@example.com", access_token: opaqueToken("opaque") },
  }], NOW);

  assert.equal(result.accounts.length, 0);
  assert.equal(result.issues.length, 1);
  assert.match(result.issues[0].reason, /account_id/);
});

test("accepts an opaque access token with account id and real id token", () => {
  const result = convertJsonDocuments([{
    sourceName: "opaque-valid.json",
    value: {
      email: "buyer@example.com",
      account_id: "account-1",
      access_token: opaqueToken("opaque"),
      id_token: "real-id-token",
    },
  }], NOW);

  assert.equal(result.issues.length, 0);
  assert.equal(result.accounts.length, 1);
  assert.equal(result.accounts[0].account.account_id, "account-1");
  assert.equal(result.accounts[0].account.id_token, "real-id-token");
  assert.equal(result.accounts[0].account.expired, "");
});

test("deduplicates accounts with an identical access token", () => {
  const sharedToken = opaqueToken("dup");
  const result = convertJsonDocuments([{
    sourceName: "duplicates.json",
    value: {
      accounts: [
        { email: "a@example.com", account_id: "a", access_token: sharedToken, id_token: "id-a" },
        { email: "b@example.com", account_id: "b", access_token: sharedToken, id_token: "id-b" },
      ],
    },
  }], NOW);

  assert.equal(result.accounts.length, 1);
  assert.equal(result.issues.length, 1);
  assert.match(result.issues[0].reason, /重复账号已跳过/);
});

test("emits expired even when a refresh token is present", () => {
  const accessToken = jwt({
    exp: 1786000000,
    "https://api.openai.com/auth": { chatgpt_account_id: "account-1" },
  });
  const result = convertJsonDocuments([{
    sourceName: "refresh.json",
    value: { account_id: "account-1", accessToken, refresh_token: "refresh-token" },
  }], NOW);

  assert.equal(result.accounts.length, 1);
  assert.equal(result.accounts[0].account.refresh_token, "refresh-token");
  assert.equal(result.accounts[0].account.expired, new Date(1786000000 * 1000).toISOString());
});

test("output matches Cockpit Tools 1.3.16 portable token shape", () => {
  const accessToken = jwt({
    exp: 1786000000,
    email: "buyer@example.com",
    "https://api.openai.com/auth": { chatgpt_account_id: "account-1" },
  });
  const result = convertJsonDocuments([{
    sourceName: "session.json",
    value: { user: { email: "buyer@example.com" }, account_id: "account-1", accessToken },
  }], NOW);
  const document = buildCockpitDocument(result.accounts);
  const idTokenPayload = JSON.parse(Buffer.from(document.id_token.split(".")[1], "base64url").toString());

  assert.equal(document.type, "codex");
  assert.deepEqual(
    Object.keys(document).sort(),
    ["access_token", "account_id", "email", "expired", "id_token", "last_refresh", "refresh_token", "type"],
  );
  assert.equal(typeof document.id_token, "string");
  assert.equal(typeof document.access_token, "string");
  assert.equal(typeof document.refresh_token, "string");
  assert.equal(typeof document.account_id, "string");
  assert.equal(typeof document.last_refresh, "string");
  assert.equal(typeof document.email, "string");
  assert.equal(typeof document.expired, "string");
  assert.equal(document.access_token, accessToken);
  assert.equal(document.account_id, "account-1");
  assert.equal(document.email, "buyer@example.com");
  assert.equal(document.expired, new Date(1786000000 * 1000).toISOString());
  assert.equal(idTokenPayload["https://api.openai.com/auth"].chatgpt_account_id, "account-1");
});

test("keeps valid files when another file fails to parse", () => {
  const result = convertJsonTexts([
    {
      sourceName: "good.json",
      text: JSON.stringify({
        email: "buyer@example.com",
        account_id: "account-1",
        access_token: opaqueToken("good"),
        id_token: "id-good",
      }),
    },
    { sourceName: "bad.json", text: "{" },
  ], NOW);

  assert.equal(result.accounts.length, 1);
  assert.equal(result.issues.length, 1);
  assert.equal(result.issues[0].sourceName, "bad.json");
  assert.match(result.issues[0].reason, /JSON 解析失败/);
});

test("stops parsing documents nested beyond the depth limit", () => {
  let value = "leaf";
  for (let index = 0; index < 80; index += 1) value = { nested: value };
  const result = convertJsonDocuments([{ sourceName: "deep.json", value }], NOW);

  assert.equal(result.accounts.length, 0);
  assert.equal(result.issues.length, 1);
  assert.match(result.issues[0].reason, /嵌套层级超过 64/);
});

test("caps the number of converted accounts per batch", () => {
  const value = {
    accounts: Array.from({ length: COCKPIT_LIMITS.maxAccountsPerBatch + 1 }, (_, index) => ({
      email: `user${index}@example.com`,
      account_id: `account-${index}`,
      access_token: opaqueToken(`token-${index}`),
      id_token: `id-${index}`,
    })),
  };
  const result = convertJsonDocuments([{ sourceName: "many.json", value }], NOW);

  assert.equal(result.accounts.length, COCKPIT_LIMITS.maxAccountsPerBatch);
  assert.equal(result.issues.length, 1);
  assert.match(result.issues[0].reason, /账号数超过单次 500/);
});

test("parses JSON text and reports invalid syntax", () => {
  assert.deepEqual(parseJsonText('{"ok":true}'), { ok: true });
  assert.throws(() => parseJsonText("{"), /JSON 解析失败/);
});
