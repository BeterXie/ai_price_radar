"use client";

import type { RelayGroup } from "@/lib/types";

export type RelayGroupDraft = RelayGroup & { models_text?: string };

export function groupInputs(groups: RelayGroupDraft[]): RelayGroup[] {
  return groups.map(({ models_text, ...group }) => {
    let models = group.models;
    if (models_text !== undefined) {
      models = models_text.trim() ? Array.from(new Set(models_text.split(/[,，]/).map((value) => value.trim()).filter(Boolean))) : null;
    }
    return { ...group, models };
  });
}

export function RelayGroupFields({ groups, onChange }: { groups: RelayGroupDraft[]; onChange: (groups: RelayGroupDraft[]) => void }) {
  const update = (index: number, patch: Partial<RelayGroupDraft>) => onChange(groups.map((group, n) => n === index ? { ...group, ...patch } : group));
  return <fieldset className="space-y-3">
    <legend className="text-sm font-medium">分组与倍率（选填）</legend>
    <p className="text-xs text-[color:var(--muted)]">优先自动同步接口资料。人工补充相同标识的分组可覆盖自动资料；倍率留空表示未公开。模型留空表示范围未知。</p>
    {groups.map((group, index) => <div key={index} className="grid gap-3 rounded-[8px] border border-[color:var(--line)] p-3 sm:grid-cols-3">
      <label className="text-xs">分组标识<input required maxLength={120} value={group.id} onChange={(e) => update(index, { id: e.target.value })} className="field mt-1 text-sm" /></label>
      <label className="text-xs">分组名称<input required maxLength={120} value={group.name} onChange={(e) => update(index, { name: e.target.value })} className="field mt-1 text-sm" /></label>
      <label className="text-xs">分组倍率（×）<input type="number" min={0} step="any" value={group.ratio ?? ""} onChange={(e) => update(index, { ratio: e.target.value === "" ? null : Number(e.target.value) })} placeholder="未公开" className="field mt-1 text-sm" /></label>
      <label className="text-xs sm:col-span-3">该组模型 ID（逗号分隔）<input value={group.models_text ?? group.models?.join(", ") ?? ""} onChange={(e) => update(index, { models_text: e.target.value })} placeholder="留空表示范围未知" className="field mt-1 text-sm" /></label>
      <button type="button" onClick={() => onChange(groups.filter((_, n) => n !== index))} className="justify-self-start text-xs underline underline-offset-4">删除分组</button>
    </div>)}
    <button type="button" disabled={groups.length >= 100} onClick={() => {
      let suffix = groups.length + 1;
      while (groups.some((group) => group.id === `group-${suffix}`)) suffix += 1;
      onChange([...groups, { id: `group-${suffix}`, name: "", ratio: null, models: null }]);
    }} className="button-secondary !min-h-8 !px-3 text-xs">添加分组</button>
  </fieldset>;
}
