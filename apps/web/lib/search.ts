export function normalizeSearchQuery(value: string): string {
  return value.normalize("NFKC").replace(/[\u200b-\u200d\ufeff]/g, "").replace(/\s+/g, " ").trim();
}

export function buildSearchHref(action: string, value: string, filters: Record<string, string> = {}): string {
  const params = new URLSearchParams(Object.entries(filters).filter(([, value]) => Boolean(value)));
  // A new search starts at the beginning of the current offer scope.
  for (const key of ["q", "page", "offset", "snapshot"]) params.delete(key);
  const query = normalizeSearchQuery(value);
  if (query) params.set("q", query);
  return `${action}${params.size ? `?${params}` : ""}`;
}
