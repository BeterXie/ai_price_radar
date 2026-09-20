export function safeExternalHttpsUrl(value: string | null | undefined): string | null {
  const raw = value?.trim() || "";
  if (!raw || /[\u0000-\u0020\u007f]/.test(raw)) return null;
  try {
    const parsed = new URL(raw);
    if (parsed.protocol !== "https:" || parsed.username || parsed.password) return null;
    return parsed.href;
  } catch {
    return null;
  }
}

export function safeInternalPath(value: string | null | undefined): string | null {
  const raw = value?.trim() || "";
  if (!raw.startsWith("/") || raw.startsWith("//") || /[\\\u0000-\u0020\u007f]/.test(raw)) return null;
  try {
    const decoded = decodeURIComponent(raw);
    const decodedPath = decoded.split(/[?#]/, 1)[0];
    if (decoded.includes("\\") || decodedPath.split("/").some((segment) => segment === "." || segment === "..")) return null;
    const parsed = new URL(raw, "https://internal.invalid");
    if (parsed.origin !== "https://internal.invalid") return null;
    return `${parsed.pathname}${parsed.search}${parsed.hash}`;
  } catch {
    return null;
  }
}

export function safeInternalDemoPath(value: string | null | undefined): string | null {
  const raw = value?.trim() || "";
  if (!raw || !raw.startsWith("/demos/") || raw.startsWith("//") || /[\\\u0000-\u0020\u007f]/.test(raw)) return null;
  try {
    const decodedSegments = decodeURIComponent(raw.split(/[?#]/, 1)[0]).split("/");
    if (decodedSegments.some((segment) => segment === "." || segment === "..")) return null;
    const parsed = new URL(raw, "https://ai.pricememo.cn");
    if (parsed.origin !== "https://ai.pricememo.cn" || parsed.search || parsed.hash || !parsed.pathname.endsWith(".html")) return null;
    return parsed.pathname;
  } catch {
    return null;
  }
}
