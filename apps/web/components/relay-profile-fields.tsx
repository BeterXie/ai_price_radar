"use client";

import type { RelayStationInput } from "@/lib/types";

type RelayProfile = Pick<RelayStationInput, "tagline" | "description" | "supported_models" | "tags" | "price_note" | "billing_note">;
export type RelayProfileDraft = Omit<RelayProfile, "supported_models" | "tags"> & { supported_models_text: string; tags_text: string };

export const EMPTY_RELAY_PROFILE: RelayProfileDraft = {
  tagline: "", description: "", supported_models_text: "", tags_text: "", price_note: "", billing_note: "",
};

function splitList(text: string): string[] {
  return Array.from(new Set(text.split(/[\n,，;；]+/).map((item) => item.trim()).filter(Boolean)));
}

export function relayProfileInputs(draft: RelayProfileDraft): RelayProfile {
  return {
    tagline: draft.tagline.trim(), description: draft.description.trim(),
    supported_models: splitList(draft.supported_models_text), tags: splitList(draft.tags_text),
    price_note: draft.price_note.trim(), billing_note: draft.billing_note.trim(),
  };
}

export function relayProfileError(draft: RelayProfileDraft): string {
  const profile = relayProfileInputs(draft);
  for (const [field, label, max] of [
    ["tagline", "一句话简介", 160], ["description", "详细说明", 2000],
    ["price_note", "价格说明", 200], ["billing_note", "计费方式", 120],
  ] as const) {
    if (!profile[field]) return `请填写${label}。`;
    if (draft[field].length > max) return `${label}最多 ${max} 个字符。`;
  }
  if (profile.supported_models.length > 40) return "支持的模型最多填写 40 个，可填写代表模型，其余由接口自动同步。";
  if (profile.supported_models.some((model) => model.length > 60)) return "每个模型 ID 最多 60 个字符。";
  if (profile.tags.length > 12) return "特性标签最多填写 12 个。";
  if (profile.tags.some((tag) => tag.length > 30)) return "每个特性标签最多 30 个字符。";
  return "";
}

export function RelayProfileFields({ value, onChange }: { value: RelayProfileDraft; onChange: (patch: Partial<RelayProfileDraft>) => void }) {
  return <fieldset className="grid gap-4 sm:grid-cols-2">
    <legend className="mb-2 text-sm font-semibold">公开展示资料</legend>
    <p className="text-xs leading-5 text-[color:var(--muted)] sm:col-span-2">以下资料供管理员审核，审核通过后公开展示。请填写真实的服务范围、价格和计费规则。</p>
    <label className="grid gap-2 text-sm font-medium sm:col-span-2" htmlFor="relay-tagline">一句话简介（必填）
      <input id="relay-tagline" required maxLength={160} value={value.tagline} onChange={(e) => onChange({ tagline: e.target.value })} placeholder="例如：OpenAI / Claude / Gemini 统一接入" className="field text-sm" />
    </label>
    <label className="grid gap-2 text-sm font-medium sm:col-span-2" htmlFor="relay-description">详细说明（必填）
      <textarea id="relay-description" required maxLength={2000} rows={4} value={value.description} onChange={(e) => onChange({ description: e.target.value })} placeholder="介绍接入方式、服务范围、余额有效期、退款规则等。" className="field resize-y text-sm" />
    </label>
    <label className="grid gap-2 text-sm font-medium sm:col-span-2" htmlFor="relay-models">支持的模型（选填）
      <textarea id="relay-models" rows={3} value={value.supported_models_text} onChange={(e) => onChange({ supported_models_text: e.target.value })} placeholder="gpt-4.1, claude-sonnet-4, gemini-2.5-pro" aria-describedby="relay-models-hint" className="field mono resize-y text-sm" />
      <span id="relay-models-hint" className="text-xs font-normal leading-5 text-[color:var(--muted)]">填写模型 ID，逗号或换行分隔，最多 40 个，每个不超过 60 字符。可填写代表模型；审核上线后会使用检测密钥自动同步可用模型，未填时以接口实际返回为准。</span>
    </label>
    <label className="grid gap-2 text-sm font-medium sm:col-span-2" htmlFor="relay-tags">特性标签（选填）
      <input id="relay-tags" value={value.tags_text} onChange={(e) => onChange({ tags_text: e.target.value })} placeholder="支持支付宝, 余额不过期" aria-describedby="relay-tags-hint" className="field text-sm" />
      <span id="relay-tags-hint" className="text-xs font-normal leading-5 text-[color:var(--muted)]">逗号分隔，最多 12 个，每个不超过 30 字符。</span>
    </label>
    <label className="grid gap-2 text-sm font-medium" htmlFor="relay-price-note">价格说明（必填）
      <input id="relay-price-note" required maxLength={200} value={value.price_note} onChange={(e) => onChange({ price_note: e.target.value })} placeholder="例如：官方价 0.7 折起 / $1 = ¥5" className="field text-sm" />
    </label>
    <label className="grid gap-2 text-sm font-medium" htmlFor="relay-billing-note">计费方式（必填）
      <input id="relay-billing-note" required maxLength={120} value={value.billing_note} onChange={(e) => onChange({ billing_note: e.target.value })} placeholder="例如：按量计费 / 包月套餐" className="field text-sm" />
    </label>
  </fieldset>;
}
