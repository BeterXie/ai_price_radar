import type { Metadata } from "next";

type VerificationEnvironment = Record<string, string | undefined>;

function clean(value: string | undefined) {
  const normalized = value?.trim();
  return normalized || undefined;
}

/**
 * Build optional search-engine verification metadata from runtime configuration.
 *
 * These values are deliberately read when metadata is generated rather than
 * being hard-coded in the repository. The prebuilt production image receives
 * them through the web container environment.
 */
export function getSearchEngineVerificationMetadata(
  environment: VerificationEnvironment = process.env,
): Metadata["verification"] | undefined {
  const other: Record<string, string> = {};
  const bingToken = clean(environment.BING_SITE_VERIFICATION);
  const baiduToken = clean(environment.BAIDU_SITE_VERIFICATION);

  if (bingToken) other["msvalidate.01"] = bingToken;
  if (baiduToken) other["baidu-site-verification"] = baiduToken;

  return Object.keys(other).length > 0 ? { other } : undefined;
}
