import { promises as fs } from "node:fs";
import path from "node:path";
import { parseAlertReport, type AlertReport } from "./alert-report";

const REPORT_LIMIT = 8 * 1024 * 1024;

async function readJson(filename: string, limit: number): Promise<unknown> {
  const handle = await fs.open(filename, "r");
  try {
    if ((await handle.stat()).size > limit) throw new Error("Alert data too large");
    const bytes = await handle.readFile();
    if (bytes.length > limit) throw new Error("Alert data too large");
    return JSON.parse(bytes.toString("utf8"));
  } finally { await handle.close(); }
}

export async function readBoundedJson(response: Response, limit: number): Promise<unknown> {
  if (!response.body) throw new Error("Empty alert response");
  const reader = response.body.getReader();
  const chunks: Uint8Array[] = [];
  let total = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      total += value.byteLength;
      if (total > limit) throw new Error("Alert data too large");
      chunks.push(value);
    }
    return JSON.parse(Buffer.concat(chunks).toString("utf8"));
  } finally { await reader.cancel(); }
}

export function currentReport(value: unknown, pointer: unknown): AlertReport {
  const report = parseAlertReport(value);
  const raw = (pointer as { snapshot_id?: unknown })?.snapshot_id;
  if (!((typeof raw === "number" && Number.isSafeInteger(raw) && raw > 0) ||
        (typeof raw === "string" && /^[1-9]\d*$/.test(raw) && Number.isSafeInteger(Number(raw)))) || Number(raw) !== report.snapshot_id) {
    throw new Error("Latest alert publication is pending");
  }
  return report;
}

/** Only the latest small report is read; the full catalog stays off this route. */
export async function getLatestAlertReport(): Promise<AlertReport | null> {
  const directory = process.env.PUBLIC_DATA_DIR || path.join(process.cwd(), "public", "data");
  try {
    const report = await readJson(path.join(directory, "alerts-latest.json"), REPORT_LIMIT);
    return currentReport(report, await readJson(path.join(directory, "latest.json"), 64 * 1024));
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
  }
  const base = (process.env.INTERNAL_API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");
  const response = await fetch(`${base}/data/alerts-latest.json`, { cache: "no-store", signal: AbortSignal.timeout(5000) });
  if (response.status === 404) return null;
  if (!response.ok) throw new Error("Alert report unavailable");
  const report = await readBoundedJson(response, REPORT_LIMIT);
  const pointer = await fetch(`${base}/data/latest.json`, { cache: "no-store", signal: AbortSignal.timeout(5000) });
  if (!pointer.ok) throw new Error("Latest catalog unavailable");
  return currentReport(report, await readBoundedJson(pointer, 64 * 1024));
}
