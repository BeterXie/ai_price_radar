// QQ Bot bridge for Dota AI Decision Lab.
//
// Loads the official @tencent-connect/qqbot-nodejs SDK from the path selected
// by the Python runtime (harness profile by default) and exposes an authenticated
// loopback HTTP API:
//   GET  /health             -> bridge/gateway status
//   GET  /events?cursor=N    -> buffered inbound messages after cursor N
//   POST /send               -> send a C2C or group text message
//
// Inbound messages are only buffered for the Python service. All command
// routing, database queries and decision rendering happen in Python.

import http from "node:http";
import crypto from "node:crypto";
import fs from "node:fs";
import { mkdir, readFile, writeFile, rename } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";

const stateDir = path.resolve(process.env.QQ_BOT_STATE_DIR || ".runtime/qq-bot");
const accountsPath = path.join(stateDir, "accounts.json");
const cursorDir = path.join(stateDir, "cursors");
const sdkIndex = process.env.QQ_BOT_SDK_INDEX;
if (!sdkIndex) {
  console.error("QQ_BOT_SDK_INDEX is required");
  process.exit(2);
}
const sdk = await import(pathToFileURL(sdkIndex).href);
const { QQBot, messageFilter, contentSanitizer, mentionGate, accessPolicy } = sdk;
const connectorIndex = process.env.QQ_BOT_CONNECTOR_INDEX || "";

const host = process.env.QQ_BOT_BRIDGE_HOST || "127.0.0.1";
const loopbackHosts = new Set(["127.0.0.1", "localhost", "::1"]);
if (!loopbackHosts.has(host)) {
  console.error("QQ_BOT_BRIDGE_HOST must remain loopback");
  process.exit(2);
}
const bridgeToken = process.env.QQ_BOT_BRIDGE_TOKEN || "";
if (bridgeToken.length < 32) {
  console.error("QQ_BOT_BRIDGE_TOKEN must be at least 32 characters");
  process.exit(2);
}
const port = Number(process.env.QQ_BOT_BRIDGE_PORT || 18081);
const preferredAccountId = process.env.QQ_BOT_ACCOUNT_ID || "";
const requireMention = process.env.QQ_BOT_GROUP_REQUIRE_MENTION !== "0";
const allowedC2C = splitList(process.env.QQ_BOT_ALLOWED_C2C);
const allowedGroups = splitList(process.env.QQ_BOT_ALLOWED_GROUPS);

const bots = new Map();
let bot = null; // preferred/first bot for commands without an explicit account id
let gatewayConnected = false;
let status = "stopped";
let statusMessage = null;
let accountCount = 0;
let accountFileSignature = null;

const eventsByAccount = new Map();
const qrSessions = new Map();
// The event buffer is in-memory, while Python persists one processed cursor per
// account. Keep the bridge cursor in the same account scope.
const eventCursors = new Map();
function loadInitialEventCursor(accountId) {
  const digest = crypto.createHash("sha1").update(accountId).digest("hex").slice(0, 16);
  const cursorFile = path.join(cursorDir, `${digest}.json`);
  try {
    const raw = JSON.parse(fs.readFileSync(cursorFile, "utf8"));
    const value = raw?.event_cursor;
    return Number.isSafeInteger(value) && value >= 0 ? value : 0;
  } catch {
    return 0;
  }
}

function currentEventCursor(accountId) {
  if (!eventCursors.has(accountId)) {
    eventCursors.set(accountId, loadInitialEventCursor(accountId));
  }
  return eventCursors.get(accountId);
}

function nextEventCursor(accountId) {
  const next = currentEventCursor(accountId) + 1;
  eventCursors.set(accountId, next);
  return next;
}
const MAX_EVENTS = 1000;

function bufferEvent(accountId, event) {
  const events = eventsByAccount.get(accountId) || [];
  events.push(event);
  if (events.length > MAX_EVENTS) events.shift();
  eventsByAccount.set(accountId, events);
}

function bufferedEventCount() {
  let count = 0;
  for (const events of eventsByAccount.values()) count += events.length;
  return count;
}

function splitList(raw) {
  return (raw || "")
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);
}

function log(level, message, meta = undefined) {
  const entry = { ts: new Date().toISOString(), level, message };
  if (meta && Object.keys(meta).length) entry.meta = meta;
  console.log(JSON.stringify(entry));
}

const sdkLogger = {
  info: (message, meta) => log("info", message, meta),
  error: (message, meta) => log("error", message, meta),
  warn: (message, meta) => log("warn", message, meta),
};

function setStatus(next, message = null) {
  status = next;
  statusMessage = message;
  log("info", `bridge_status=${next}${message ? ` message=${message}` : ""}`);
}

function authorized(req) {
  const header = req.headers.authorization;
  if (typeof header !== "string" || !header.startsWith("Bearer ")) return false;
  const supplied = header.slice("Bearer ".length);
  const expectedBytes = Buffer.from(bridgeToken, "utf8");
  const suppliedBytes = Buffer.from(supplied, "utf8");
  return (
    expectedBytes.length === suppliedBytes.length &&
    crypto.timingSafeEqual(expectedBytes, suppliedBytes)
  );
}

async function readAccounts() {
  try {
    const raw = JSON.parse(await readFile(accountsPath, "utf8"));
    const accounts = Array.isArray(raw) ? raw : [];
    accountCount = accounts.filter(
      (item) => item && typeof item.app_id === "string" && typeof item.app_secret === "string",
    ).length;
    return accounts.filter(
      (item) => item && typeof item.app_id === "string" && typeof item.app_secret === "string",
    );
  } catch (error) {
    accountCount = 0;
    return [];
  }
}

function safeTimestamp(raw) {
  if (raw === undefined || raw === null) return null;
  const value = Number(raw);
  if (!Number.isFinite(value)) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

function enqueueMessage(accountId, msg) {
  const scope = msg.kind === "c2c" ? "c2c" : "group";
  const mentions = Array.isArray(msg.mentions)
    ? msg.mentions
        .filter((mention) => mention && typeof mention === "object")
        .map((mention) => mention.id || mention.user_openid || mention.member_openid || "")
        .filter(Boolean)
    : [];
  const botMentioned = Array.isArray(msg.mentions)
    ? msg.mentions.some((mention) => mention && (mention.is_you === true || mention.bot === true))
    : false;
  const event = {
    account_id: accountId,
    event_type: "MESSAGE",
    event_cursor: nextEventCursor(accountId),
    scope,
    target_id: scope === "c2c" ? msg.senderId : msg.groupOpenid,
    sender_id: msg.senderId,
    message_id: msg.messageId,
    text: msg.content || "",
    sender_name: msg.senderName || null,
    bot_mentioned: botMentioned,
    mentions,
    timestamp: safeTimestamp(msg.timestamp),
  };
  bufferEvent(accountId, event);
  log("info", "qq_event_buffered", {
    cursor: event.event_cursor,
    scope: event.scope,
    target_id: event.target_id,
  });
}

function enqueueFriendAdd(accountId, raw) {
  const openid = firstString(
    raw?.openid,
    raw?.open_id,
    raw?.user_openid,
    raw?.userOpenid,
    raw?.sender_id,
    raw?.author?.openid,
    raw?.author?.user_openid,
  );
  if (!openid) return;
  const callbackData = firstString(
    raw?.scene_param,
    raw?.sceneParam,
    raw?.callback_data,
    raw?.callbackData,
  );
  const event = {
    account_id: accountId,
    event_type: "FRIEND_ADD",
    event_cursor: nextEventCursor(accountId),
    scope: "c2c",
    target_id: openid,
    sender_id: openid,
    message_id: null,
    text: "",
    scene_param: callbackData || null,
    sender_name: firstString(raw?.author?.nick, raw?.author?.nickname, raw?.nickname) || null,
    bot_mentioned: false,
    mentions: [],
    timestamp: safeTimestamp(
      (() => {
        const value = Number(raw?.timestamp || 0);
        return value > 0 && value < 1_000_000_000_000 ? value * 1000 : value;
      })(),
    ),
  };
  bufferEvent(accountId, event);
  log("info", "qq_friend_added", {
    cursor: event.event_cursor,
    scene: raw?.scene || null,
    has_callback_data: Boolean(callbackData),
  });
}

function firstString(...values) {
  for (const value of values) {
    if (typeof value === "string" && value.trim()) return value.trim();
  }
  return "";
}

function buildBot(account) {
  const controller = new AbortController();
  const accountId = account.app_id;
  const sessionFile = path.join(stateDir, `gateway-session-${safeFilePart(accountId)}.json`);
  const instance = new QQBot({
    appId: account.app_id,
    appSecret: account.app_secret,
    accountId: account.app_id,
    logger: sdkLogger,
    userAgent: "Dota-AI-Decision-Lab/0.1.0",
    sessionPersistence: {
      load: () => {
        try {
          if (!fs.existsSync(sessionFile)) return null;
          return JSON.parse(fs.readFileSync(sessionFile, "utf8"));
        } catch {
          return null;
        }
      },
      save: (session) => {
        try {
          fs.mkdirSync(stateDir, { recursive: true });
          const temp = `${sessionFile}.tmp`;
          fs.writeFileSync(temp, JSON.stringify(session));
          fs.renameSync(temp, sessionFile);
        } catch (error) {
          log("warn", "session_save_failed", { error: String(error) });
        }
      },
      clear: () => {
        try {
          fs.rmSync(sessionFile, { force: true });
        } catch {
          // Session cleanup is best-effort.
        }
      },
    },
  });

  instance.on("ready", (data) => {
    const state = bots.get(accountId);
    if (state) state.connected = true;
    refreshGatewayStatus();
    log("info", "gateway_ready", { sessionId: data?.session_id || null });
  });
  instance.on("resumed", () => {
    const state = bots.get(accountId);
    if (state) state.connected = true;
    refreshGatewayStatus();
  });
  instance.on("error", (error) => {
    const state = bots.get(accountId);
    if (state) state.connected = false;
    refreshGatewayStatus(String(error?.message || error));
  });
  instance.on("message", (_ctx, msg) => {
      try {
        enqueueMessage(accountId, msg);
    } catch (error) {
      log("error", "message_buffer_failed", { error: String(error) });
    }
  });
  instance.on("rawEvent", (ctx) => {
    if (ctx?.eventType !== "FRIEND_ADD") return;
      try {
        enqueueFriendAdd(accountId, ctx.data || ctx.payload || ctx);
    } catch (error) {
      log("error", "friend_add_buffer_failed", { error: String(error) });
    }
  });

  const policy = {};
  if (allowedC2C.length) {
    policy.c2c = { mode: "allowlist", allow: allowedC2C };
  }
  if (allowedGroups.length) policy.group = { mode: "allowlist", allow: allowedGroups };
  if (Object.keys(policy).length) instance.use(accessPolicy(policy));
  instance.use(messageFilter({ skipSelfEcho: true, dedup: { windowMs: 5000, maxSize: 1000 } }));
  instance.use(contentSanitizer({ collapseWhitespace: true }));
  instance.use(mentionGate({ requireMentionInGroup: requireMention }));

  setStatus("STARTING");
  const state = {
    account,
    instance,
    controller,
    connected: false,
    startPromise: null,
  };
  state.startPromise = instance
    .start(controller.signal)
    .then(() => {
      state.connected = false;
      refreshGatewayStatus();
    })
    .catch((error) => {
      state.connected = false;
      refreshGatewayStatus(String(error?.message || error));
      log("error", "bot_start_failed", {
        accountId,
        error: String(error?.stack || error),
      });
    });
  bots.set(accountId, state);
  if (!bot || accountId === preferredAccountId) bot = instance;
  log("info", "bot_started", { appId: accountId });
}

async function stopBot() {
  const states = [...bots.values()];
  bots.clear();
  bot = null;
  await Promise.all(states.map(async (state) => {
    try {
      state.controller.abort();
      state.instance.stop();
      await state.startPromise;
    } catch {
      // A stopped bridge must not propagate shutdown races.
    }
  }));
  gatewayConnected = false;
  status = "STOPPED";
}

function refreshGatewayStatus(errorMessage = null) {
  gatewayConnected = [...bots.values()].some((state) => state.connected);
  if (gatewayConnected) {
    setStatus("READY");
  } else if (bots.size) {
    setStatus("DEGRADED", errorMessage || "no QQ account is connected");
  } else {
    setStatus("ACTION_REQUIRED", "scan a QQ QR code to bind an account");
  }
}

async function startFromAccounts() {
  const accounts = await readAccounts();
  if (!accounts.length) {
    await stopBot();
    setStatus("ACTION_REQUIRED", "scan a QQ QR code to bind an account");
    return;
  }
  await stopBot();
  for (const account of accounts) buildBot(account);
}

function safeFilePart(value) {
  return String(value).replace(/[^A-Za-z0-9_.-]/g, "_").slice(0, 120) || "account";
}

function selectedBot(accountId = "") {
  // An explicit account id is an isolation boundary for user-owned
  // notifications. Never silently route a stale binding through another bot.
  if (accountId) return bots.get(accountId) || null;
  const state = (preferredAccountId && bots.get(preferredAccountId)) || bots.values().next().value;
  if (!state) return null;
  return state;
}

function sendJson(res, code, body) {
  const payload = JSON.stringify(body);
  res.writeHead(code, {
    "Content-Type": "application/json; charset=utf-8",
    "Content-Length": Buffer.byteLength(payload),
  });
  res.end(payload);
}

async function readJsonBody(req, limit = 1024 * 1024) {
  const chunks = [];
  let size = 0;
  for await (const chunk of req) {
    size += chunk.length;
    if (size > limit) throw new Error("request body too large");
    chunks.push(chunk);
  }
  if (!chunks.length) return {};
  return JSON.parse(Buffer.concat(chunks).toString("utf8"));
}

async function sendMessage(body) {
  const state = selectedBot(typeof body.account_id === "string" ? body.account_id : "");
  if (!state || !state.connected) {
    const error = new Error("QQ bridge is not connected to the QQ gateway");
    error.statusCode = 503;
    throw error;
  }
  if (body.scope !== "c2c" && body.scope !== "group") {
    const error = new Error("scope must be c2c or group");
    error.statusCode = 400;
    throw error;
  }
  const target = { scope: body.scope, targetId: body.target_id };
  if (body.msg_id) target.msgId = body.msg_id;
  const response = await state.instance.sendText(target, body.text);
  return {
    message_id: response?.id || null,
    timestamp: response?.timestamp || null,
  };
}

const outboxDir = path.join(stateDir, "outbox");
// Concurrent HTTP requests with the same idempotency key must share one send,
// otherwise both miss the cache, both send, and both compete for the same .tmp file.
const inFlightSends = new Map();
async function idempotentSend(body) {
  if (!body.idempotency_key) return sendMessage(body);
  const digest = crypto
    .createHash("sha256")
    .update(`${body.account_id || ""}\u0000${body.scope || ""}\u0000${body.target_id || ""}\u0000${body.idempotency_key}`)
    .digest("hex")
    .slice(0, 48);
  const file = path.join(outboxDir, `${digest}.json`);
  try {
    return JSON.parse(await readFile(file, "utf8"));
  } catch {
    // First send for this idempotency key.
  }

  const pending = inFlightSends.get(digest);
  if (pending) return pending;

  const task = (async () => {
    try {
      const result = await sendMessage(body);
      await mkdir(outboxDir, { recursive: true });
      const temp = `${file}.${process.pid}.${Date.now()}.tmp`;
      await writeFile(temp, JSON.stringify(result));
      await rename(temp, file);
      return result;
    } finally {
      // Always release the in-flight slot, including on failure, so a retry
      // after an error is not permanently blocked.
      inFlightSends.delete(digest);
    }
  })();
  inFlightSends.set(digest, task);
  return task;
}

async function ensureConnector() {
  if (!connectorIndex) {
    const error = new Error("QQ QR connector is not installed");
    error.statusCode = 503;
    throw error;
  }
  if (!fs.existsSync(connectorIndex)) {
    const error = new Error(`QQ QR connector entry not found: ${connectorIndex}`);
    error.statusCode = 503;
    throw error;
  }
  return import(pathToFileURL(connectorIndex).href);
}

async function startQrBinding() {
  const connector = await ensureConnector();
  const sessionId = crypto.randomBytes(18).toString("base64url");
  let qrReady = false;
  let qrReadyTimer = null;
  let resolveQrReady = () => {};
  const waitForQr = new Promise((resolve) => {
    resolveQrReady = resolve;
    qrReadyTimer = setTimeout(settleQrReady, 5_000);
  });
  function settleQrReady() {
    if (qrReady) return;
    qrReady = true;
    if (qrReadyTimer !== null) clearTimeout(qrReadyTimer);
    resolveQrReady();
  }
  const session = {
    session_id: sessionId,
    status: "WAITING",
    qrcode_url: null,
    credentials: null,
    message: null,
    created_at: new Date().toISOString(),
    expires_at: new Date(Date.now() + 5 * 60 * 1000).toISOString(),
    stop: null,
  };
  const stop = connector.startQrConnect(
    {
      onQrDisplayed: (url) => {
        session.qrcode_url = url;
        session.status = "WAITING";
        settleQrReady();
      },
      onQrExpired: () => {
        session.status = "WAITING";
        session.message = "二维码已刷新";
      },
      onSuccess: (credentials) => {
        if (["CANCELLED", "EXPIRED"].includes(session.status)) {
          settleQrReady();
          return;
        }
        const credential = Array.isArray(credentials) ? credentials[0] : null;
        if (!credential?.appId || !credential?.appSecret) {
          session.status = "FAILED";
          session.message = "QQ 扫码未返回完整账号凭据";
        } else {
          session.status = "COMPLETED";
          session.credentials = {
            app_id: String(credential.appId),
            app_secret: String(credential.appSecret),
            user_openid: firstString(credential.userOpenid, credential.user_open_id) || null,
          };
          session.message = "QQ 账号扫码成功";
        }
        session.stop?.();
        settleQrReady();
      },
      onFailure: (error) => {
        if (["CANCELLED", "EXPIRED"].includes(session.status)) {
          settleQrReady();
          return;
        }
        session.status = "FAILED";
        session.message = String(error?.message || error || "QQ 扫码失败");
        settleQrReady();
      },
    },
    { displayQrCodeToConsole: false },
  );
  session.stop = stop;
  qrSessions.set(sessionId, session);
  await waitForQr;
  return qrPayload(session, true);
}

function qrPayload(session, includeCredentials = false) {
  return {
    session_id: session.session_id,
    status: session.status,
    qrcode_url: session.qrcode_url,
    created_at: session.created_at,
    expires_at: session.expires_at,
    message: session.message,
    ...(includeCredentials && session.credentials ? { credentials: session.credentials } : {}),
  };
}

function qrStatus(sessionId) {
  const session = qrSessions.get(sessionId);
  if (!session) {
    const error = new Error("QQ QR session not found");
    error.statusCode = 404;
    throw error;
  }
  if (Date.parse(session.expires_at) <= Date.now() && !["COMPLETED", "FAILED"].includes(session.status)) {
    session.status = "EXPIRED";
    session.message = "二维码已过期，请重新生成";
    session.stop?.();
  }
  return qrPayload(session, true);
}

function cancelQrBinding(sessionId) {
  const session = qrSessions.get(sessionId);
  if (!session) {
    const error = new Error("QQ QR session not found");
    error.statusCode = 404;
    throw error;
  }
  session.status = "CANCELLED";
  session.message = "已取消扫码绑定";
  session.stop?.();
  return qrPayload(session, false);
}

// IPv6 literals must be bracketed in a URL authority, otherwise parsing
// "http://::1:18081" throws and takes the whole request (and process) down.
const baseAuthority = host.includes(":") ? `[${host}]` : host;

const server = http.createServer(async (req, res) => {
  try {
    let url;
    try {
      url = new URL(req.url || "/", `http://${baseAuthority}:${port}`);
    } catch (urlError) {
      log("error", "invalid_request_url", { url: req.url, error: String(urlError?.message) });
      sendJson(res, 400, { error: "invalid request url" });
      return;
    }
    if (!authorized(req)) {
      sendJson(res, 401, { error: "unauthorized" });
      return;
    }
    if (req.method === "GET" && url.pathname === "/health") {
      sendJson(res, 200, {
        ok: gatewayConnected,
        status,
        message: statusMessage,
        account_count: accountCount,
        gateway_connected: gatewayConnected,
        buffered_events: bufferedEventCount(),
      });
      return;
    }
    if (req.method === "GET" && url.pathname === "/events") {
      const accountId = url.searchParams.get("account_id") || "";
      if (!accountId) {
        sendJson(res, 400, { error: "account_id is required" });
        return;
      }
      const cursor = Number(url.searchParams.get("cursor") || 0);
      const outgoing = (eventsByAccount.get(accountId) || []).filter(
        (event) => event.event_cursor > cursor,
      );
      sendJson(res, 200, { events: outgoing, cursor: currentEventCursor(accountId) });
      return;
    }
    if (req.method === "POST" && url.pathname === "/send") {
      const body = await readJsonBody(req);
      if (!body.scope || !body.target_id || typeof body.text !== "string" || !body.text.trim()) {
        sendJson(res, 400, { error: "scope, target_id and non-empty text are required" });
        return;
      }
      if (body.account_id !== undefined && body.account_id !== null && typeof body.account_id !== "string") {
        sendJson(res, 400, { error: "account_id must be a string when provided" });
        return;
      }
      const result = await idempotentSend(body);
      sendJson(res, 200, result);
      return;
    }
    if (req.method === "POST" && url.pathname === "/qr/start") {
      sendJson(res, 200, await startQrBinding());
      return;
    }
    if (req.method === "GET" && url.pathname === "/qr/status") {
      const sessionId = url.searchParams.get("session_id") || "";
      sendJson(res, 200, qrStatus(sessionId));
      return;
    }
    if (req.method === "POST" && url.pathname === "/qr/cancel") {
      const body = await readJsonBody(req);
      sendJson(res, 200, cancelQrBinding(String(body.session_id || "")));
      return;
    }
    sendJson(res, 404, { error: "not found" });
  } catch (error) {
    const statusCode = error.statusCode || 500;
    if (statusCode >= 500) log("error", "http_request_failed", { error: String(error?.stack || error) });
    sendJson(res, statusCode, { error: String(error?.message || error) });
  }
});

server.listen(port, host, () => {
  log("info", "bridge_http_listening", { host, port, sdkIndex });
});

let reloadInFlight = null;
let reloadPending = false;

async function reloadAccounts() {
  // Serialize reloads: an overlapping poll must never start a second
  // startFromAccounts while the previous one is still awaiting stopBot,
  // which would leave duplicate connections that stopBot cannot manage.
  if (reloadInFlight) {
    reloadPending = true;
    return reloadInFlight;
  }
  reloadInFlight = (async () => {
    try {
      do {
        reloadPending = false;
        let signature = "missing";
        try {
          const stat = await fs.promises.stat(accountsPath);
          signature = `${stat.mtimeMs}:${stat.size}`;
        } catch {
          // The Python store creates accounts.json after the first QR login.
        }
        if (signature === accountFileSignature) continue;
        try {
          await startFromAccounts();
          accountFileSignature = signature;
        } catch (error) {
          setStatus("DEGRADED", String(error?.message || error));
          log("error", "account_reload_failed", { error: String(error?.stack || error) });
        }
      } while (reloadPending);
    } finally {
      reloadInFlight = null;
    }
  })();
  return reloadInFlight;
}

await reloadAccounts();
// Cloud Storage FUSE does not guarantee that fs.watchFile receives a native
// filesystem notification. Poll the small account manifest instead so a QR
// binding written by Python is picked up on both local disks and the Cloud Run
// mounted bucket.
const accountReloadTimer = setInterval(() => {
  void reloadAccounts();
}, 2000);
accountReloadTimer.unref();

async function shutdown(signal) {
  log("info", "bridge_shutdown", { signal });
  clearInterval(accountReloadTimer);
  await stopBot();
  server.close(() => process.exit(0));
  setTimeout(() => process.exit(0), 3000).unref();
}
process.on("SIGINT", () => shutdown("SIGINT"));
process.on("SIGTERM", () => shutdown("SIGTERM"));
