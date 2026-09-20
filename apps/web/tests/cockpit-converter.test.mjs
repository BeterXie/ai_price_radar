import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
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
  const firstIdToken = jwt({
    email: "one@example.com",
    "https://api.openai.com/auth": { chatgpt_account_id: "one" },
  });
  const result = convertJsonDocuments([{
    sourceName: "batch.json",
    value: {
      accounts: [
        { email: "one@example.com", account_id: "one", access_token: opaqueToken("one"), id_token: firstIdToken },
        { meta: { label: "two@example.com" }, tokens: { access_token: opaqueToken("two"), account_id: "two", refresh_token: "refresh-two" } },
      ],
    },
  }], NOW);

  assert.equal(result.issues.length, 0);
  assert.equal(result.accounts.length, 2);
  assert.deepEqual(buildCockpitDocument(result.accounts), [
    {
      type: "codex",
      id_token: firstIdToken,
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

test("supports top-level accountId and camelCase credentials fields", () => {
  const result = convertJsonDocuments([
    {
      sourceName: "top-level.json",
      value: {
        email: "top@example.com",
        accountId: "top-account",
        accessToken: opaqueToken("top"),
      },
    },
    {
      sourceName: "credentials.json",
      value: {
        credentials: {
          email: "credentials@example.com",
          accountId: "credentials-account",
          accessToken: opaqueToken("credentials"),
          refreshToken: "refresh-credentials",
        },
      },
    },
  ], NOW);

  assert.equal(result.issues.length, 0);
  assert.deepEqual(result.accounts.map((item) => item.account.account_id), ["top-account", "credentials-account"]);
  assert.equal(result.accounts[1].account.refresh_token, "refresh-credentials");
});

test("rejects conflicting record, access token, and id token identities", () => {
  const accessToken = jwt({
    email: "access@example.com",
    "https://api.openai.com/auth": {
      chatgpt_account_id: "access-account",
      chatgpt_user_id: "access-user",
    },
  });
  const idToken = jwt({
    email: "id@example.com",
    "https://api.openai.com/auth": {
      chatgpt_account_id: "id-account",
      chatgpt_user_id: "id-user",
    },
  });
  const result = convertJsonDocuments([{
    sourceName: "conflict.json",
    value: {
      email: "record@example.com",
      account_id: "record-account",
      user_id: "record-user",
      access_token: accessToken,
      id_token: idToken,
    },
  }], NOW);

  assert.equal(result.accounts.length, 0);
  assert.equal(result.issues.length, 1);
  assert.match(result.issues[0].reason, /身份字段互相冲突/);
});

test("ignores a non-email label and falls back to a valid token email", () => {
  const accessToken = jwt({
    email: "claim@example.com",
    "https://api.openai.com/auth": { chatgpt_account_id: "claim-account" },
  });
  const valid = convertJsonDocuments([{
    sourceName: "label-with-claim.json",
    value: { label: "个人账号", access_token: accessToken },
  }], NOW);
  assert.equal(valid.accounts.length, 1);
  assert.equal(valid.accounts[0].account.email, "claim@example.com");

  const invalid = convertJsonDocuments([{
    sourceName: "label-only.json",
    value: { label: "个人账号", account_id: "label-account", access_token: opaqueToken("label") },
  }], NOW);
  assert.equal(invalid.accounts.length, 0);
  assert.match(invalid.issues[0].reason, /缺少 email/);
});

test("keeps scanning nested accounts after an invalid outer candidate", () => {
  const result = convertJsonDocuments([{
    sourceName: "wrapped.json",
    value: {
      email: "outer@example.com",
      access_token: "too-short",
      accounts: [{
        email: "inner@example.com",
        account_id: "inner-account",
        access_token: opaqueToken("inner"),
      }],
    },
  }], NOW);

  assert.equal(result.accounts.length, 1);
  assert.equal(result.accounts[0].account.account_id, "inner-account");
  assert.ok(result.issues.some((issue) => /accessToken 长度不足/.test(issue.reason)));
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

test("replaces an unparsable id_token with a synthetic token", () => {
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
  assert.notEqual(result.accounts[0].account.id_token, "real-id-token");
  assert.match(result.accounts[0].account.id_token, /\.synthetic$/);
  const payload = JSON.parse(Buffer.from(result.accounts[0].account.id_token.split(".")[1], "base64url").toString());
  assert.equal(payload.email, "buyer@example.com");
  assert.equal(result.accounts[0].account.expired, "");
});

test("keeps a parseable id_token that contains email", () => {
  const idToken = jwt({
    email: "buyer@example.com",
    "https://api.openai.com/auth": { chatgpt_account_id: "account-1" },
  });
  const result = convertJsonDocuments([{
    sourceName: "real-id.json",
    value: {
      email: "buyer@example.com",
      account_id: "account-1",
      access_token: opaqueToken("opaque"),
      id_token: idToken,
    },
  }], NOW);

  assert.equal(result.issues.length, 0);
  assert.equal(result.accounts[0].account.id_token, idToken);
});

test("rejects accounts without email", () => {
  const result = convertJsonDocuments([{
    sourceName: "no-email.json",
    value: { account_id: "account-1", access_token: opaqueToken("opaque") },
  }], NOW);

  assert.equal(result.accounts.length, 0);
  assert.equal(result.issues.length, 1);
  assert.match(result.issues[0].reason, /缺少 email/);
});

test("rejects an identical access token assigned to another account", () => {
  const sharedToken = opaqueToken("dup");
  const result = convertJsonDocuments([{
    sourceName: "duplicates.json",
    value: {
      accounts: [
        { email: "a@example.com", account_id: "a", access_token: sharedToken },
        { email: "b@example.com", account_id: "b", access_token: sharedToken },
      ],
    },
  }], NOW);

  assert.equal(result.accounts.length, 1);
  assert.equal(result.issues.length, 1);
  assert.match(result.issues[0].reason, /access_token 已关联到另一个 account_id/);
});

test("deduplicates rotated tokens by account id and keeps the newer expiry", () => {
  const olderToken = jwt({
    email: "rotated@example.com",
    exp: 1786000000,
    "https://api.openai.com/auth": { chatgpt_account_id: "rotated-account" },
  });
  const newerToken = jwt({
    email: "rotated@example.com",
    exp: 1886000000,
    "https://api.openai.com/auth": { chatgpt_account_id: "rotated-account" },
  });
  const result = convertJsonDocuments([{
    sourceName: "rotation.json",
    value: {
      accounts: [
        { email: "rotated@example.com", account_id: "rotated-account", access_token: olderToken },
        { email: "rotated@example.com", account_id: "rotated-account", access_token: newerToken },
      ],
    },
  }], NOW);

  assert.equal(result.accounts.length, 1);
  assert.equal(result.accounts[0].account.access_token, newerToken);
  assert.match(result.issues[0].reason, /令牌已轮换/);
});

test("emits expired even when a refresh token is present", () => {
  const accessToken = jwt({
    exp: 1786000000,
    "https://api.openai.com/auth": { chatgpt_account_id: "account-1" },
  });
  const result = convertJsonDocuments([{
    sourceName: "refresh.json",
    value: { email: "buyer@example.com", account_id: "account-1", accessToken, refresh_token: "refresh-token" },
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
  assert.deepEqual(result.parsedFileNames, ["good.json"]);
});

test("stops parsing documents nested beyond the depth limit", () => {
  let value = "leaf";
  for (let index = 0; index < 80; index += 1) value = { nested: value };
  const result = convertJsonDocuments([{ sourceName: "deep.json", value }], NOW);

  assert.equal(result.accounts.length, 0);
  assert.equal(result.issues.length, 1);
  assert.match(result.issues[0].reason, /嵌套层级超过 64/);
});

test("counts scalar array entries against the traversal budget", () => {
  const value = Array.from({ length: COCKPIT_LIMITS.maxVisitedNodes }, () => 0);
  const result = convertJsonDocuments([{ sourceName: "scalars.json", value }], NOW);

  assert.equal(result.accounts.length, 0);
  assert.ok(result.issues.some((issue) => /对象节点数超过/.test(issue.reason)));
});

test("shares the traversal budget across files", () => {
  const half = Math.ceil(COCKPIT_LIMITS.maxVisitedNodes / 2);
  const result = convertJsonDocuments([
    { sourceName: "first-scalars.json", value: Array.from({ length: half }, () => 0) },
    { sourceName: "second-scalars.json", value: Array.from({ length: half }, () => 0) },
  ], NOW);

  assert.ok(result.issues.some((issue) => issue.sourceName === "second-scalars.json" && /对象节点数超过/.test(issue.reason)));
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
  assert.match(result.issues[0].reason, /已达到单次批次 500/);
});

test("caps total accounts across multiple files", () => {
  const firstFile = {
    accounts: Array.from({ length: COCKPIT_LIMITS.maxAccountsPerBatch }, (_, index) => ({
      email: `user${index}@example.com`,
      account_id: `account-${index}`,
      access_token: opaqueToken(`token-${index}`),
      id_token: `id-${index}`,
    })),
  };
  const result = convertJsonDocuments([
    { sourceName: "first.json", value: firstFile },
    {
      sourceName: "second.json",
      value: { email: "extra@example.com", account_id: "extra", access_token: opaqueToken("extra") },
    },
  ], NOW);

  assert.equal(result.accounts.length, COCKPIT_LIMITS.maxAccountsPerBatch);
  assert.equal(result.issues.length, 1);
  assert.match(result.issues[0].reason, /已达到单次批次 500/);
});

test("invalid records do not consume the account budget", () => {
  const records = Array.from({ length: COCKPIT_LIMITS.maxAccountsPerBatch }, (_, index) => ({
    email: `bad${index}@example.com`,
    access_token: opaqueToken(`bad-${index}`),
  }));
  records.push({
    email: "good@example.com",
    account_id: "good",
    access_token: opaqueToken("good"),
  });
  const result = convertJsonDocuments([{
    sourceName: "mixed.json",
    value: { accounts: records },
  }], NOW);

  assert.equal(result.accounts.length, 1);
  assert.equal(result.accounts[0].account.account_id, "good");
  assert.ok(result.issues.some((issue) => /account_id/.test(issue.reason)));
});

test("duplicate records do not consume the account budget", () => {
  const sharedToken = opaqueToken("dup");
  const records = Array.from({ length: COCKPIT_LIMITS.maxAccountsPerBatch + 10 }, () => ({
    email: "dup@example.com",
    account_id: "dup",
    access_token: sharedToken,
  }));
  records.push({
    email: "good@example.com",
    account_id: "good",
    access_token: opaqueToken("good"),
  });
  const result = convertJsonDocuments([{
    sourceName: "duplicates.json",
    value: { accounts: records },
  }], NOW);

  assert.equal(result.accounts.length, 2);
  assert.equal(result.accounts[0].account.account_id, "dup");
  assert.equal(result.accounts[1].account.account_id, "good");
});

test("caps reported conversion issues", () => {
  const value = {
    accounts: Array.from({ length: COCKPIT_LIMITS.maxIssuesPerBatch + 100 }, (_, index) => ({
      email: `invalid${index}@example.com`,
      account_id: `invalid-${index}`,
      access_token: "too-short",
    })),
  };
  const result = convertJsonDocuments([{ sourceName: "many-invalid.json", value }], NOW);

  assert.equal(result.issues.length, COCKPIT_LIMITS.maxIssuesPerBatch);
  assert.match(result.issues.at(-1).reason, /问题上限/);
});

test("parses JSON text and reports invalid syntax", () => {
  assert.deepEqual(parseJsonText('{"ok":true}'), { ok: true });
  assert.throws(() => parseJsonText("{"), /JSON 解析失败/);
  assert.throws(
    () => parseJsonText(" ".repeat(COCKPIT_LIMITS.maxPastedTextBytes + 1)),
    /JSON 文本超过 10 MB 上限/,
  );
});

test("converter UI invalidates stale reads and disables analytics on the credential route", async () => {
  const converterSource = await readFile(new URL("../components/guides/cockpit-json-converter.tsx", import.meta.url), "utf8");
  const analyticsSource = await readFile(new URL("../components/google-analytics.tsx", import.meta.url), "utf8");

  assert.match(converterSource, /const generation = \+\+readGenerationRef\.current/);
  assert.match(converterSource, /generation !== readGenerationRef\.current/);
  assert.match(converterSource, /function clearAll\(\): void \{\s*readGenerationRef\.current \+= 1/);
  assert.match(converterSource, /useEffect\(\(\) => \(\) => \{\s*readGenerationRef\.current \+= 1/);
  assert.match(converterSource, /event\.target\.value = ""/);
  assert.match(analyticsSource, /"\/tools\/json-to-cockpit"/);
});
