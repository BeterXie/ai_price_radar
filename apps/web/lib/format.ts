export function money(value: string | number | null, currency = "CNY") {
  if (value === null || value === undefined || value === "") return "暂无有货价";
  return new Intl.NumberFormat("zh-CN", {
    style: "currency",
    currency,
    currencyDisplay: "narrowSymbol",
    minimumFractionDigits: 2,
  }).format(Number(value));
}

export function exactTime(value: string | null) {
  if (!value) return "暂无";
  const date = new Date(value);
  const parts = new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(date);
  const get = (type: Intl.DateTimeFormatPartTypes) => parts.find((part) => part.type === type)?.value || "";
  return `${get("year")}-${get("month")}-${get("day")} ${get("hour")}:${get("minute")} 北京时间`;
}

export function relativeTime(value: string | null) {
  if (!value) return "暂无更新";
  const diff = Date.now() - new Date(value).getTime();
  const minutes = Math.max(0, Math.floor(diff / 60000));
  if (minutes < 1) return "刚刚";
  if (minutes < 60) return `${minutes} 分钟前`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} 小时前`;
  const days = Math.floor(hours / 24);
  return `${days} 天前`;
}

export function stockLabel(status: string) {
  return ({
    in_stock: "有货",
    out_of_stock: "缺货",
    unavailable: "不可用",
    unknown: "库存未知",
  } as Record<string, string>)[status] || status;
}
