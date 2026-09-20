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
  maxPastedTextBytes: 10 * 1024 * 1024,
  maxTotalFileBytes: 10 * 1024 * 1024,
  maxFilesPerBatch: 50,
  maxDepth: 64,
  maxVisitedNodes: 200_000,
  maxAccountsPerBatch: 500,
  maxIssuesPerBatch: 500,
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

export interface JsonTextConversionResult extends CockpitConversionResult {
  parsedFileNames: readonly string[];
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

function normalizedEmail(value: unknown): string | undefined {
  if (typeof value !== "string") return undefined;
  const cleaned = value.trim();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(cleaned)) return undefined;
  return cleaned;
}

function firstEmail(...values: readonly unknown[]): string | undefined {
  for (const value of values) {
    const email = normalizedEmail(value);
    if (email) return email;
  }
  return undefined;
}

function assertConsistentIdentity(label: string, values: readonly (string | undefined)[], normalize = (value: string) => value): void {
  const distinct = new Set(values.filter((value): value is string => Boolean(value)).map(normalize));
  if (distinct.size > 1) throw new Error(`${label} 身份字段互相冲突`);
}

function readString(record: UnknownRecord, ...paths: readonly (readonly string[])[]): string | undefined {
  return firstString(...paths.map((path) => valueAt(record, path)));
}

function createIssueCollector() {
  const issues: CockpitConversionIssue[] = [];
  let omitted = 0;

  return {
    add(issue: CockpitConversionIssue): void {
      if (issues.length < COCKPIT_LIMITS.maxIssuesPerBatch - 1) {
        issues.push(issue);
      } else {
        omitted += 1;
      }
    },
    result(): readonly CockpitConversionIssue[] {
      if (!omitted) return issues;
      return [
        ...issues,
        {
          sourceName: "批次",
          path: "$",
          reason: `另有 ${omitted} 个问题未逐项显示，已达到 ${COCKPIT_LIMITS.maxIssuesPerBatch} 条问题上限`,
        },
      ];
    },
  };
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

type TraversalBudget = { visitedNodes: number };

function collectSessionRecords(
  value: unknown,
  budget: TraversalBudget,
): readonly { record: UnknownRecord; path: string }[] {
  const found: { record: UnknownRecord; path: string }[] = [];
  const visited = new WeakSet<object>();

  function visit(item: unknown, path: string, depth: number): void {
    budget.visitedNodes += 1;
    if (budget.visitedNodes > COCKPIT_LIMITS.maxVisitedNodes) {
      throw new Error(`对象节点数超过 ${COCKPIT_LIMITS.maxVisitedNodes}，已停止解析`);
    }
    if (!isRecord(item) && !Array.isArray(item)) return;
    if (visited.has(item)) return;
    visited.add(item);
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
        item.account_id,
        item.accountId,
        valueAt(item, ["meta", "label"]),
        valueAt(item, ["account", "id"]),
        valueAt(item, ["tokens", "account_id"]),
        valueAt(item, ["providerSpecificData", "chatgptAccountId"]),
        valueAt(item, ["credentials", "email"]),
        valueAt(item, ["credentials", "accountId"]),
        valueAt(item, ["credentials", "account_id"]),
        valueAt(item, ["credentials", "chatgptAccountId"]),
        valueAt(item, ["credentials", "chatgpt_account_id"]),
        payload?.email,
        auth.chatgpt_account_id,
      ));
      const isCandidate = Boolean(accessToken && hasIdentity);
      if (isCandidate) {
        found.push({ record: item, path });
      }
      for (const [key, child] of Object.entries(item)) {
        if (["accessToken", "access_token", "sessionToken", "session_token"].includes(key)) continue;
        if (isCandidate && ["account", "credentials", "meta", "providerSpecificData", "token", "tokens", "user"].includes(key)) {
          continue;
        }
        visit(child, `${path}.${key}`, depth + 1);
      }
      return;
    }

    item.forEach((child, index) => visit(child, `${path}[${index}]`, depth + 1));
  }

  visit(value, "$", 0);
  return found;
}

function validateCockpitAccount(
  accessToken: string,
  accountId: string | undefined,
  email: string | undefined,
): readonly string[] {
  const reasons: string[] = [];
  if (accessToken.length < COCKPIT_LIMITS.minAccessTokenLength) {
    reasons.push(`accessToken 长度不足（至少 ${COCKPIT_LIMITS.minAccessTokenLength} 个字符）`);
  } else if (accessToken.length > COCKPIT_LIMITS.maxAccessTokenLength) {
    reasons.push(`accessToken 长度超过 ${COCKPIT_LIMITS.maxAccessTokenLength} 个字符上限`);
  }
  if (!accountId) {
    reasons.push("缺少 account_id，无法从账号信息或令牌中识别");
  }
  if (!email) {
    reasons.push("缺少 email，无法生成可导入的 id_token");
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
    ["credentials", "refreshToken"],
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
    ["credentials", "idToken"],
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
  const recordEmail = firstEmail(
    valueAt(record, ["user", "email"]),
    record.email,
    valueAt(record, ["meta", "label"]),
    record.label,
    valueAt(record, ["credentials", "email"]),
    valueAt(record, ["providerSpecificData", "email"]),
  );
  const accessEmail = firstEmail(profile.email, payload?.email);
  const idEmail = firstEmail(idPayload?.email);
  assertConsistentIdentity("email", [recordEmail, accessEmail, idEmail], (value) => value.toLowerCase());
  const email = firstEmail(recordEmail, accessEmail, idEmail);

  const recordAccountId = firstString(
    valueAt(record, ["account", "id"]),
    record.accountId,
    record.account_id,
    valueAt(record, ["tokens", "accountId"]),
    valueAt(record, ["tokens", "account_id"]),
    record.chatgptAccountId,
    record.chatgpt_account_id,
    valueAt(record, ["meta", "chatgptAccountId"]),
    valueAt(record, ["meta", "chatgpt_account_id"]),
    valueAt(record, ["providerSpecificData", "chatgptAccountId"]),
    valueAt(record, ["providerSpecificData", "chatgpt_account_id"]),
    valueAt(record, ["credentials", "accountId"]),
    valueAt(record, ["credentials", "account_id"]),
    valueAt(record, ["credentials", "chatgptAccountId"]),
    valueAt(record, ["credentials", "chatgpt_account_id"]),
    record.provider === "codex" ? record.id : undefined,
  );
  const accessAccountId = firstString(auth.chatgpt_account_id);
  const idAccountId = firstString(idAuth.chatgpt_account_id);
  assertConsistentIdentity("account_id", [recordAccountId, accessAccountId, idAccountId]);
  const accountId = firstString(recordAccountId, accessAccountId, idAccountId);

  const recordUserId = firstString(
    valueAt(record, ["user", "id"]),
    record.user_id,
    record.chatgptUserId,
    record.chatgpt_user_id,
    valueAt(record, ["providerSpecificData", "chatgptUserId"]),
    valueAt(record, ["credentials", "userId"]),
    valueAt(record, ["credentials", "user_id"]),
    valueAt(record, ["credentials", "chatgptUserId"]),
    valueAt(record, ["credentials", "chatgpt_user_id"]),
  );
  const accessUserId = firstString(auth.chatgpt_user_id, auth.user_id);
  const idUserId = firstString(idAuth.chatgpt_user_id, idAuth.user_id);
  assertConsistentIdentity("user_id", [recordUserId, accessUserId, idUserId]);
  const userId = firstString(recordUserId, accessUserId, idUserId);
  const planType = firstString(
    valueAt(record, ["account", "planType"]),
    valueAt(record, ["account", "plan_type"]),
    record.planType,
    record.plan_type,
    valueAt(record, ["providerSpecificData", "chatgptPlanType"]),
    valueAt(record, ["providerSpecificData", "chatgpt_plan_type"]),
    valueAt(record, ["credentials", "planType"]),
    valueAt(record, ["credentials", "plan_type"]),
    valueAt(record, ["credentials", "chatgptPlanType"]),
    valueAt(record, ["credentials", "chatgpt_plan_type"]),
    auth.chatgpt_plan_type,
    idAuth.chatgpt_plan_type,
  );

  const validationReasons = validateCockpitAccount(accessToken, accountId, email);
  if (validationReasons.length) {
    throw new Error(validationReasons.join("；"));
  }

  const canKeepInputIdToken = Boolean(inputIdToken && idPayload && idEmail);
  const idToken = canKeepInputIdToken
    ? inputIdToken
    : syntheticIdToken(email, accountId, planType, userId, expiresAt, now);
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
  const issueCollector = createIssueCollector();
  const seenAccessTokens = new Map<string, string>();
  const accountIndexes = new Map<string, number>();
  const traversalBudget: TraversalBudget = { visitedNodes: 0 };
  let budgetExceededReported = false;

  function shouldReplaceAccount(
    existing: ConvertedCockpitAccount,
    candidate: ConvertedCockpitAccount,
  ): boolean {
    const existingExpiry = Date.parse(existing.expiresAt || "");
    const candidateExpiry = Date.parse(candidate.expiresAt || "");
    const existingRank = Number.isFinite(existingExpiry) ? existingExpiry : Number.NEGATIVE_INFINITY;
    const candidateRank = Number.isFinite(candidateExpiry) ? candidateExpiry : Number.NEGATIVE_INFINITY;
    if (candidateRank !== existingRank) return candidateRank > existingRank;
    return true;
  }

  for (const document of documents) {
    let records: readonly { record: UnknownRecord; path: string }[];
    try {
      records = collectSessionRecords(document.value, traversalBudget);
    } catch (error) {
      issueCollector.add({
        sourceName: document.sourceName,
        path: "$",
        reason: error instanceof Error ? error.message : "解析失败",
      });
      continue;
    }
    if (!records.length) {
      issueCollector.add({ sourceName: document.sourceName, path: "$", reason: "未找到包含 accessToken 和账号信息的对象" });
      continue;
    }
    for (const { record, path } of records) {
      try {
        const converted = convertRecord(record, document.sourceName, path, now);
        const accountId = converted.account.account_id;
        const tokenOwner = seenAccessTokens.get(converted.account.access_token);
        if (tokenOwner) {
          issueCollector.add({
            sourceName: document.sourceName,
            path,
            reason: tokenOwner === accountId
              ? "重复账号已跳过（access_token 相同）"
              : "access_token 已关联到另一个 account_id，记录已跳过",
          });
          continue;
        }

        seenAccessTokens.set(converted.account.access_token, accountId);
        const existingIndex = accountIndexes.get(accountId);
        if (existingIndex !== undefined) {
          const existing = accounts[existingIndex];
          if (shouldReplaceAccount(existing, converted)) {
            accounts[existingIndex] = converted;
            issueCollector.add({
              sourceName: document.sourceName,
              path,
              reason: "同一 account_id 的令牌已轮换，保留到期时间较晚或后出现的记录",
            });
          } else {
            issueCollector.add({
              sourceName: document.sourceName,
              path,
              reason: "同一 account_id 的较旧令牌已跳过",
            });
          }
          continue;
        }

        if (accounts.length >= COCKPIT_LIMITS.maxAccountsPerBatch) {
          if (!budgetExceededReported) {
            issueCollector.add({
              sourceName: document.sourceName,
              path: "$",
              reason: `账号总数已达到单次批次 ${COCKPIT_LIMITS.maxAccountsPerBatch} 个上限，后续新账号不再转换`,
            });
            budgetExceededReported = true;
          }
          continue;
        }

        accountIndexes.set(accountId, accounts.length);
        accounts.push(converted);
      } catch (error) {
        issueCollector.add({
          sourceName: document.sourceName,
          path,
          reason: error instanceof Error ? error.message : "无法转换",
        });
      }
    }
  }

  return { accounts, issues: issueCollector.result() };
}

export function convertJsonTexts(documents: readonly JsonTextDocument[], now = new Date()): JsonTextConversionResult {
  const parsedDocuments: JsonDocument[] = [];
  const parseIssueCollector = createIssueCollector();

  for (const document of documents) {
    try {
      parsedDocuments.push({ sourceName: document.sourceName, value: parseJsonText(document.text) });
    } catch (error) {
      parseIssueCollector.add({
        sourceName: document.sourceName,
        path: "$",
        reason: error instanceof Error ? error.message : "JSON 解析失败",
      });
    }
  }

  const converted = convertJsonDocuments(parsedDocuments, now);
  const combinedIssueCollector = createIssueCollector();
  converted.issues.forEach((issue) => combinedIssueCollector.add(issue));
  parseIssueCollector.result().forEach((issue) => combinedIssueCollector.add(issue));
  return {
    accounts: converted.accounts,
    issues: combinedIssueCollector.result(),
    parsedFileNames: parsedDocuments.map((document) => document.sourceName),
  };
}

export function parseJsonText(text: string): unknown {
  const byteLength = new TextEncoder().encode(text).byteLength;
  if (byteLength > COCKPIT_LIMITS.maxPastedTextBytes) {
    throw new Error(`JSON 文本超过 ${COCKPIT_LIMITS.maxPastedTextBytes / (1024 * 1024)} MB 上限`);
  }
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
