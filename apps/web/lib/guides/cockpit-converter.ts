/**
 * Cockpit field mapping is adapted from the MIT-licensed
 * gtxx3600/GPTSession2CPAandSub2API project and reimplemented here as a
 * Cockpit-only, browser-local converter.
 *
 * The generated portable token shape follows Cockpit Tools v1.3.16
 * (CodexPortableTokenStorage in src/utils/codexExportFormats.ts).
 */

type UnknownRecord = Record<string, unknown>;

export const COCKPIT_LIMITS = {
  maxFileBytes: 10 * 1024 * 1024,
  maxFilesPerBatch: 50,
  maxDepth: 64,
  maxVisitedNodes: 200_000,
  maxAccountsPerBatch: 500,
  minAccessTokenLength: 40,
  maxAccessTokenLength: 100_000,
} as const;

export interface CockpitAccount {
  type: "codex";
  id_token: string;
  access_token: string;
  refresh_token: string;
  account_id: string;
  last_refresh: string;
  email: string;
  expired: string;
  account_note?: string;
}

export interface CockpitConversionIssue {
  sourceName: string;
  path: string;
  reason: string;
}

export interface ConvertedCockpitAccount {
  account: CockpitAccount;
  sourceName: string;
  sourcePath: string;
  email?: string;
  expiresAt?: string;
}

export interface CockpitConversionResult {
  accounts: readonly ConvertedCockpitAccount[];
  issues: readonly CockpitConversionIssue[];
}

export interface JsonDocument {
  sourceName: string;
  value: unknown;
}

export interface JsonTextDocument {
  sourceName: string;
  text: string;
}

function isRecord(value: unknown): value is UnknownRecord {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function valueAt(record: UnknownRecord, path: readonly string[]): unknown {
  let current: unknown = record;
  for (const key of path) {
    if (!isRecord(current)) return undefined;
    current = current[key];
  }
  return current;
}

function firstString(...values: readonly unknown[]): string | undefined {
  for (const value of values) {
    if (typeof value === "string" && value.trim()) return value.trim();
  }
  return undefined;
}

function readString(record: UnknownRecord, ...paths: readonly (readonly string[])[]): string | undefined {
  return firstString(...paths.map((path) => valueAt(record, path)));
}

function decodeBase64Url(value: string): string {
  const normalized = value.replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");
  const binary = atob(padded);
  const bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0));
  return new TextDecoder().decode(bytes);
}

function encodeBase64UrlJson(value: unknown): string {
  const bytes = new TextEncoder().encode(JSON.stringify(value));
  let binary = "";
  for (let index = 0; index < bytes.length; index += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(index, index + 0x8000));
  }
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function parseJwtPayload(token: string | undefined): UnknownRecord | undefined {
  if (!token) return undefined;
  const segments = token.split(".");
  if (segments.length < 2) return undefined;
  try {
    const payload: unknown = JSON.parse(decodeBase64Url(segments[1]));
    return isRecord(payload) ? payload : undefined;
  } catch {
    return undefined;
  }
}

function recordSection(record: UnknownRecord | undefined, key: string): UnknownRecord {
  if (!record) return {};
  const section = record[key];
  return isRecord(section) ? section : {};
}

function normalizeTimestamp(value: unknown): string | undefined {
  if (value instanceof Date && !Number.isNaN(value.getTime())) return value.toISOString();
  if (typeof value === "number" && Number.isFinite(value)) {
    const milliseconds = value > 1e11 ? value : value * 1000;
    const date = new Date(milliseconds);
    return Number.isNaN(date.getTime()) ? undefined : date.toISOString();
  }
  if (typeof value !== "string" || !value.trim()) return undefined;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? undefined : date.toISOString();
}

function timestampFromUnixSeconds(value: unknown): string | undefined {
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric <= 0) return undefined;
  return new Date(numeric * 1000).toISOString();
}

function epochSeconds(value: string | undefined): number {
  if (!value) return 0;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? Math.trunc(parsed / 1000) : 0;
}

function syntheticIdToken(
  email: string | undefined,
  accountId: string | undefined,
  planType: string | undefined,
  userId: string | undefined,
  expiresAt: string | undefined,
  now: Date,
): string | undefined {
  if (!accountId) return undefined;
  const issuedAt = Math.trunc(now.getTime() / 1000);
  const auth: UnknownRecord = { chatgpt_account_id: accountId };
  if (planType) auth.chatgpt_plan_type = planType;
  if (userId) {
    auth.chatgpt_user_id = userId;
    auth.user_id = userId;
  }
  const payload: UnknownRecord = {
    iat: issuedAt,
    exp: epochSeconds(expiresAt) || issuedAt + 90 * 24 * 60 * 60,
    "https://api.openai.com/auth": auth,
  };
  if (email) payload.email = email;
  return `${encodeBase64UrlJson({ alg: "none", typ: "JWT", cpa_synthetic: true })}.${encodeBase64UrlJson(payload)}.synthetic`;
}

function accessTokenOf(record: UnknownRecord): string | undefined {
  return readString(
    record,
    ["accessToken"],
    ["access_token"],
    ["tokens", "accessToken"],
    ["tokens", "access_token"],
    ["token", "accessToken"],
    ["token", "access_token"],
    ["credentials", "accessToken"],
    ["credentials", "access_token"],
  );
}

function collectSessionRecords(value: unknown): readonly { record: UnknownRecord; path: string }[] {
  const found: { record: UnknownRecord; path: string }[] = [];
  const visited = new WeakSet<object>();
  let visitedNodes = 0;

  function visit(item: unknown, path: string, depth: number): void {
    if (!isRecord(item) && !Array.isArray(item)) return;
    if (visited.has(item)) return;
    visited.add(item);
    visitedNodes += 1;
    if (visitedNodes > COCKPIT_LIMITS.maxVisitedNodes) {
      throw new Error(`对象节点数超过 ${COCKPIT_LIMITS.maxVisitedNodes}，已停止解析`);
    }
    if (depth > COCKPIT_LIMITS.maxDepth) {
      throw new Error(`嵌套层级超过 ${COCKPIT_LIMITS.maxDepth} 层，已停止解析`);
    }

    if (isRecord(item)) {
      const accessToken = accessTokenOf(item);
      const payload = parseJwtPayload(accessToken);
      const auth = recordSection(payload, "https://api.openai.com/auth");
      const hasIdentity = isRecord(item.user) || Boolean(firstString(
        item.email,
        item.name,
        item.label,
        valueAt(item, ["meta", "label"]),
        valueAt(item, ["account", "id"]),
        valueAt(item, ["tokens", "account_id"]),
        valueAt(item, ["providerSpecificData", "chatgptAccountId"]),
        payload?.email,
        auth.chatgpt_account_id,
      ));
      if (accessToken && hasIdentity) {
        found.push({ record: item, path });
        return;
      }
      for (const [key, child] of Object.entries(item)) {
        if (["accessToken", "access_token", "sessionToken", "session_token"].includes(key)) continue;
        visit(child, `${path}.${key}`, depth + 1);
      }
      return;
    }

    item.forEach((child, index) => visit(child, `${path}[${index}]`, depth + 1));
  }

  visit(value, "$", 0);
  return found;
}

function validateCockpitAccount(accessToken: string, accountId: string | undefined): readonly string[] {
  const reasons: string[] = [];
  if (accessToken.length < COCKPIT_LIMITS.minAccessTokenLength) {
    reasons.push(`accessToken 长度不足（至少 ${COCKPIT_LIMITS.minAccessTokenLength} 个字符）`);
  } else if (accessToken.length > COCKPIT_LIMITS.maxAccessTokenLength) {
    reasons.push(`accessToken 长度超过 ${COCKPIT_LIMITS.maxAccessTokenLength} 个字符上限`);
  }
  if (!accountId) {
    reasons.push("缺少 account_id，无法从账号信息或令牌中识别");
  }
  return reasons;
}

function convertRecord(record: UnknownRecord, sourceName: string, sourcePath: string, now: Date): ConvertedCockpitAccount {
  const accessToken = accessTokenOf(record);
  if (!accessToken) throw new Error("缺少 accessToken");

  const refreshToken = readString(
    record,
    ["refreshToken"],
    ["refresh_token"],
    ["tokens", "refreshToken"],
    ["tokens", "refresh_token"],
    ["token", "refreshToken"],
    ["token", "refresh_token"],
    ["credentials", "refresh_token"],
  );
  const inputIdToken = readString(
    record,
    ["idToken"],
    ["id_token"],
    ["tokens", "idToken"],
    ["tokens", "id_token"],
    ["token", "idToken"],
    ["token", "id_token"],
    ["credentials", "id_token"],
  );
  const payload = parseJwtPayload(accessToken);
  const idPayload = parseJwtPayload(inputIdToken);
  const auth = recordSection(payload, "https://api.openai.com/auth");
  const idAuth = recordSection(idPayload, "https://api.openai.com/auth");
  const profile = recordSection(payload, "https://api.openai.com/profile");
  const expiresAt = firstString(
    payload ? timestampFromUnixSeconds(payload.exp) : undefined,
    normalizeTimestamp(record.expires),
    normalizeTimestamp(record.expiresAt),
    normalizeTimestamp(record.expired),
    normalizeTimestamp(record.expires_at),
  );
  const email = firstString(
    valueAt(record, ["user", "email"]),
    record.email,
    valueAt(record, ["meta", "label"]),
    record.label,
    valueAt(record, ["credentials", "email"]),
    valueAt(record, ["providerSpecificData", "email"]),
    profile.email,
    idPayload?.email,
    payload?.email,
  );
  const accountId = firstString(
    valueAt(record, ["account", "id"]),
    record.account_id,
    valueAt(record, ["tokens", "accountId"]),
    valueAt(record, ["tokens", "account_id"]),
    record.chatgptAccountId,
    record.chatgpt_account_id,
    valueAt(record, ["meta", "chatgptAccountId"]),
    valueAt(record, ["meta", "chatgpt_account_id"]),
    valueAt(record, ["providerSpecificData", "chatgptAccountId"]),
    valueAt(record, ["providerSpecificData", "chatgpt_account_id"]),
    valueAt(record, ["credentials", "chatgpt_account_id"]),
    auth.chatgpt_account_id,
    idAuth.chatgpt_account_id,
    record.provider === "codex" ? record.id : undefined,
  );
  const userId = firstString(
    valueAt(record, ["user", "id"]),
    record.user_id,
    record.chatgptUserId,
    valueAt(record, ["providerSpecificData", "chatgptUserId"]),
    auth.chatgpt_user_id,
    auth.user_id,
    idAuth.chatgpt_user_id,
    idAuth.user_id,
  );
  const planType = firstString(
    valueAt(record, ["account", "planType"]),
    valueAt(record, ["account", "plan_type"]),
    record.planType,
    record.plan_type,
    valueAt(record, ["providerSpecificData", "chatgptPlanType"]),
    valueAt(record, ["providerSpecificData", "chatgpt_plan_type"]),
    valueAt(record, ["credentials", "plan_type"]),
    auth.chatgpt_plan_type,
    idAuth.chatgpt_plan_type,
  );

  const validationReasons = validateCockpitAccount(accessToken, accountId);
  if (validationReasons.length) {
    throw new Error(validationReasons.join("；"));
  }

  const idToken = inputIdToken ?? syntheticIdToken(email, accountId, planType, userId, expiresAt, now);
  const account: CockpitAccount = {
    type: "codex",
    id_token: idToken ?? "",
    access_token: accessToken,
    refresh_token: refreshToken ?? "",
    account_id: accountId ?? "",
    last_refresh: now.toISOString(),
    email: email ?? "",
    expired: expiresAt ?? "",
  };
  const note = firstString(record.account_note, record.accountInfo, record.account_info, record.note, record.notes, record.remark);
  if (note) account.account_note = note;

  return { account, sourceName, sourcePath, email, expiresAt };
}

export function convertJsonDocuments(documents: readonly JsonDocument[], now = new Date()): CockpitConversionResult {
  const accounts: ConvertedCockpitAccount[] = [];
  const issues: CockpitConversionIssue[] = [];
  const seenAccessTokens = new Set<string>();

  for (const document of documents) {
    let records: readonly { record: UnknownRecord; path: string }[];
    try {
      records = collectSessionRecords(document.value);
    } catch (error) {
      issues.push({
        sourceName: document.sourceName,
        path: "$",
        reason: error instanceof Error ? error.message : "解析失败",
      });
      continue;
    }
    if (!records.length) {
      issues.push({ sourceName: document.sourceName, path: "$", reason: "未找到包含 accessToken 和账号信息的对象" });
      continue;
    }
    const boundedRecords = records.slice(0, COCKPIT_LIMITS.maxAccountsPerBatch);
    if (records.length > boundedRecords.length) {
      issues.push({
        sourceName: document.sourceName,
        path: "$",
        reason: `账号数超过单次 ${COCKPIT_LIMITS.maxAccountsPerBatch} 个上限，已转换前 ${COCKPIT_LIMITS.maxAccountsPerBatch} 个`,
      });
    }
    for (const { record, path } of boundedRecords) {
      try {
        const converted = convertRecord(record, document.sourceName, path, now);
        if (seenAccessTokens.has(converted.account.access_token)) {
          issues.push({ sourceName: document.sourceName, path, reason: "重复账号已跳过（access_token 相同）" });
          continue;
        }
        seenAccessTokens.add(converted.account.access_token);
        accounts.push(converted);
      } catch (error) {
        issues.push({
          sourceName: document.sourceName,
          path,
          reason: error instanceof Error ? error.message : "无法转换",
        });
      }
    }
  }

  return { accounts, issues };
}

export function convertJsonTexts(documents: readonly JsonTextDocument[], now = new Date()): CockpitConversionResult {
  const parsedDocuments: JsonDocument[] = [];
  const parseIssues: CockpitConversionIssue[] = [];

  for (const document of documents) {
    try {
      parsedDocuments.push({ sourceName: document.sourceName, value: parseJsonText(document.text) });
    } catch (error) {
      parseIssues.push({
        sourceName: document.sourceName,
        path: "$",
        reason: error instanceof Error ? error.message : "JSON 解析失败",
      });
    }
  }

  const converted = convertJsonDocuments(parsedDocuments, now);
  return { accounts: converted.accounts, issues: [...converted.issues, ...parseIssues] };
}

export function parseJsonText(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch (error) {
    throw new Error(`JSON 解析失败：${error instanceof Error ? error.message : "格式不正确"}`);
  }
}

export function buildCockpitDocument(accounts: readonly ConvertedCockpitAccount[]): CockpitAccount | readonly CockpitAccount[] {
  const output = accounts.map((item) => item.account);
  return output.length === 1 ? output[0] : output;
}
