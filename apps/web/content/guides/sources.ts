import type { OfficialSource } from "@/lib/guides/types";

export const LAST_REVIEWED_AT = "2026-08-03";

export const GUIDE_DISCLAIMER =
  "AI Price Radar 只整理公开商品信息和一般使用知识，不参与交易、支付、交付或售后。第三方商品可能存在账号控制权、服务稳定性、官方条款和隐私风险。购买前请返回商品原页面确认价格、期限、交付和售后条件。";

function officialSource(title: string, url: string, publisher: string): OfficialSource {
  return { title, url, publisher, lastCheckedAt: LAST_REVIEWED_AT };
}

export const OFFICIAL_SOURCES = {
  openaiHelp: officialSource("OpenAI Help Center", "https://help.openai.com/", "OpenAI"),
  openaiKeySafety: officialSource(
    "Best Practices for API Key Safety",
    "https://help.openai.com/en/articles/5112595-best-practices-for-api-key-safety",
    "OpenAI",
  ),
  openaiPlatform: officialSource("OpenAI API Documentation", "https://platform.openai.com/docs/", "OpenAI"),
  openaiTerms: officialSource("OpenAI Terms of Use", "https://openai.com/policies/terms-of-use/", "OpenAI"),
  anthropicHelp: officialSource("Anthropic Help Center", "https://support.anthropic.com/", "Anthropic"),
  anthropicDocs: officialSource("Claude API Documentation", "https://docs.anthropic.com/", "Anthropic"),
  anthropicTerms: officialSource("Anthropic Legal Center", "https://www.anthropic.com/legal", "Anthropic"),
  geminiHelp: officialSource("Gemini Apps Help", "https://support.google.com/gemini/", "Google"),
  geminiApi: officialSource("Gemini API Documentation", "https://ai.google.dev/gemini-api/docs", "Google"),
  googleAccount: officialSource("Google Account Help", "https://support.google.com/accounts/", "Google"),
  grokHelp: officialSource("xAI Help Center", "https://help.x.ai/", "xAI"),
  grokApi: officialSource("xAI API Documentation", "https://docs.x.ai/", "xAI"),
  xHelp: officialSource("X Help Center", "https://help.x.com/", "X"),
  xTerms: officialSource("X Terms of Service", "https://x.com/en/tos", "X"),
} as const;
