export interface PolicyRequestInput {
  source_url: string;
  request_type: "opt_out" | "correction" | "ownership";
  requester_email: string;
  reason: string;
}

export function normalizePublicHttpsUrl(value: string): string | null {
  const raw = value.trim();
  if (!raw) return null;
  let candidate = raw;
  if (!/^[a-z][a-z0-9+.-]*:\/\//i.test(candidate)) {
    candidate = `https://${candidate}`;
  }
  let parsed: URL;
  try {
    parsed = new URL(candidate);
  } catch {
    return null;
  }
  if (parsed.protocol === "http:") {
    parsed.protocol = "https:";
  }
  if (parsed.protocol !== "https:" || !parsed.hostname) return null;
  if (parsed.username || parsed.password) return null;
  if (parsed.port && parsed.port !== "443") return null;
  if (parsed.hostname === "localhost" || parsed.hostname.endsWith(".local") || parsed.hostname.endsWith(".internal")) return null;
  if (!isPublicHostname(parsed.hostname)) return null;
  parsed.hash = "";
  return parsed.toString();
}

function isPublicHostname(hostname: string): boolean {
  const ipv4 = hostname.match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/);
  if (ipv4) {
    const parts = ipv4.slice(1).map(Number);
    if (parts.some((part) => part > 255)) return false;
    const [a, b] = parts;
    if (a === 0 || a === 10 || a === 127 || a >= 224) return false;
    if (a === 169 && b === 254) return false;
    if (a === 172 && b >= 16 && b <= 31) return false;
    if (a === 192 && b === 168) return false;
    return true;
  }
  return !hostname.includes(":");
}

export function validatePolicyRequest(input: PolicyRequestInput): string | null {
  if (!normalizePublicHttpsUrl(input.source_url)) return "请输入有效的公开 HTTPS 来源地址。";
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(input.requester_email.trim())) return "请输入有效的联系邮箱。";
  if (!["opt_out", "correction", "ownership"].includes(input.request_type)) return "请选择请求类型。";
  return null;
}
