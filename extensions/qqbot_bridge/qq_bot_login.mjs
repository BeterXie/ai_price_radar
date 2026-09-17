// One-time QQ Bot QR login helper.
//
// Uses the official @tencent-connect/qqbot-connector installed by the
// harness profile.  The QR code is printed to the console; after the owner
// scans it with phone QQ the AppID/AppSecret are persisted to the QQ state
// directory and this process exits 0.

import { mkdir, readFile, writeFile, rename } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";

const stateDir = path.resolve(process.env.QQ_BOT_STATE_DIR || ".runtime/qq-bot");
const accountsPath = path.join(stateDir, "accounts.json");
const connectorIndex = process.env.QQ_BOT_CONNECTOR_INDEX;
if (!connectorIndex) {
  console.error("QQ_BOT_CONNECTOR_INDEX is required");
  process.exit(2);
}
const { startQrConnect } = await import(pathToFileURL(connectorIndex).href);

const credentials = await new Promise((resolve, reject) => {
  startQrConnect(
    {
      onSuccess: resolve,
      onFailure: reject,
      onQrDisplayed: (url) => {
        console.log(`📱 绑定链接: ${url}`);
        console.log("   也可直接扫描终端中的二维码。");
      },
      onQrExpired: () => {
        console.log("二维码已过期，正在刷新…");
      },
    },
    { displayQrCodeToConsole: true, source: "" },
  );
});
if (!Array.isArray(credentials) || credentials.length === 0) {
  console.error("QR login completed without credentials");
  process.exit(1);
}

await mkdir(stateDir, { recursive: true });
const rows = [];
try {
  const existing = JSON.parse(await readFile(accountsPath, "utf8"));
  if (Array.isArray(existing)) rows.push(...existing);
} catch {
  // First account.
}

for (const credential of credentials) {
  const account = {
    app_id: String(credential.appId || "").trim(),
    app_secret: String(credential.appSecret || ""),
    user_openid: String(credential.userOpenid || "").trim() || null,
    created_at: new Date().toISOString(),
  };
  if (!account.app_id || !account.app_secret) {
    console.error("QR login returned an incomplete credential");
    process.exit(1);
  }
  const index = rows.findIndex((item) => item && item.app_id === account.app_id);
  if (index >= 0) rows[index] = account;
  else rows.push(account);
}

const temp = `${accountsPath}.tmp`;
await writeFile(temp, JSON.stringify(rows, null, 2));
await rename(temp, accountsPath);
console.log(`✅ QQ Bot bound: ${rows.map((item) => item.app_id).join(", ")}`);
