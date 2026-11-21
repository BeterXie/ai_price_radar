export type AlertView = "drops" | "rises" | "team";

export type AlertOffer = {
  offer_id: number;
  product_name: string;
  product_slug: string;
  shop_name: string;
  price: string;
  currency: string;
  observed_at: string;
  old_price?: string;
  diff?: string;
  percent_change?: number;
  ends_at?: string;
  is_head_car?: boolean;
};

export type AlertReport = {
  schema_version: "price-radar.alerts.v1";
  snapshot_id: number;
  published_at: string;
  stale_offer_hours: number;
  drops: AlertOffer[];
  rises: AlertOffer[];
  team: AlertOffer[];
};

export const ALERT_VIEWS = [
  { key: "drops", label: "降价榜" },
  { key: "rises", label: "涨价动态" },
  { key: "team", label: "Team 车提醒" },
] as const;

export function alertView(value: unknown): AlertView {
  return value === "team" || value === "rises" ? value : "drops";
}

export function parseAlertReport(value: unknown): AlertReport {
  const report = value as AlertReport;
  if (!report || report.schema_version !== "price-radar.alerts.v1" ||
      !Number.isSafeInteger(report.snapshot_id) || report.snapshot_id < 1 ||
      !isoTimestamp(report.published_at) ||
      !Number.isInteger(report.stale_offer_hours) || report.stale_offer_hours < 1 || report.stale_offer_hours > 720) {
    throw new Error("Invalid alert report");
  }
  for (const { key } of ALERT_VIEWS) {
    if (!Array.isArray(report[key]) || report[key].some((row) =>
      !row || !Number.isSafeInteger(row.offer_id) || row.offer_id < 1 ||
      typeof row.product_name !== "string" || typeof row.shop_name !== "string" ||
      typeof row.product_slug !== "string" || typeof row.currency !== "string" ||
      !decimalString(row.price) || Number(row.price) <= 0 ||
      !isoTimestamp(row.observed_at) ||
      (key === "team" ? !isoTimestamp(row.ends_at) || typeof row.is_head_car !== "boolean" :
        !decimalString(row.old_price) || Number(row.old_price) < 0 ||
        !decimalString(row.diff) || !Number.isFinite(row.percent_change))
    )) throw new Error("Invalid alert items");
  }
  return report;
}

function decimalString(value: unknown): value is string {
  return typeof value === "string" && /^-?\d+(?:\.\d+)?$/.test(value) && Number.isFinite(Number(value));
}

function isoTimestamp(value: unknown): value is string {
  return typeof value === "string" && /^\d{4}-\d{2}-\d{2}T.+(?:Z|[+-]\d{2}:\d{2})$/.test(value) && Number.isFinite(Date.parse(value));
}

export function serverAlignedNow(initialNow: number, elapsed: number): number {
  return initialNow + Math.max(0, elapsed);
}

export function nextAlertExpiry(report: AlertReport, now: number): number {
  return Math.min(now + 60_000, ...[...report.drops, ...report.rises, ...report.team].flatMap((row) =>
    [Date.parse(row.observed_at) + report.stale_offer_hours * 3_600_000 + 1,
      ...(row.ends_at ? [Date.parse(row.ends_at)] : [])].filter((time) => time > now)));
}

export function currentAlertRows(report: AlertReport, view: AlertView, now: number): AlertOffer[] {
  const cutoff = now - report.stale_offer_hours * 3_600_000;
  return report[view].filter((row) => Date.parse(row.observed_at) >= cutoff &&
    (view !== "team" || (row.ends_at && Date.parse(row.ends_at) > now)));
}

export function alertMoney(value: string | number, currency = "CNY"): string {
  let prefix = `${currency} `;
  if (currency === "CNY" || currency === "RMB") prefix = "¥";
  else if (currency === "USD") prefix = "$";
  return `${prefix}${Number(value).toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

const beijingTime = new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23",
});

export function alertTime(value: string): string {
  return beijingTime.format(new Date(value));
}
