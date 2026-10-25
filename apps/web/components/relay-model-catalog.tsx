"use client";

import { useState } from "react";
import { exactTime, relativeTime } from "@/lib/format";
import { modelsForGroup } from "@/lib/relay-groups";
import type { RelayGroup, RelayModelCatalog as Catalog } from "@/lib/types";

const SYNC_MESSAGES: Record<string, string> = {
  timeout: "最近同步超时",
  unsupported: "站点暂未提供模型列表接口",
  credential_error: "模型列表接口未授权",
};

export function RelayModelCatalog({ catalog, group, now }: { catalog: Catalog; group?: RelayGroup | null; now?: number }) {
  const [query, setQuery] = useState("");
  const [limit, setLimit] = useState(20);
  const hasGroupModels = group?.models !== null && group?.models !== undefined;
  if (!catalog?.checked_at && !hasGroupModels) return null;
  const needle = query.trim().toLocaleLowerCase();
  const scopedModels = modelsForGroup(catalog?.models || [], group);
  const models = scopedModels.filter((model) => [model.id, model.name, model.provider, model.description].some((value) => value.toLocaleLowerCase().includes(needle)));
  let scopeHint = "清单以该密钥的接口返回为准；";
  if (hasGroupModels) scopeHint = "模型范围来自该分组资料；";
  else if (group) scopeHint = "接口未提供该组的模型范围，以下仍为当前密钥可见清单；";
  let syncHint = "";
  if (catalog?.checked_at && catalog.status !== "ok") {
    syncHint = SYNC_MESSAGES[catalog.status] || "最近同步未成功";
    if (hasGroupModels) syncHint += "；仅影响模型详情，模型范围按所选分组资料展示。";
    else syncHint += catalog.synced_at ? "，以下保留上次同步的清单。" : "。";
  }
  return (
    <section className="mt-3 min-w-0" aria-label="密钥可见模型目录">
      <p className="text-xs text-[color:var(--muted)]">
        {hasGroupModels ? `${group.name} · ${scopedModels.length} 个模型` : ""}
        {!hasGroupModels && catalog.synced_at ? <>接口返回 {catalog.models.length}{catalog.truncated ? "+" : ""} 个模型 · <time dateTime={catalog.synced_at} title={exactTime(catalog.synced_at)}>{relativeTime(catalog.synced_at, now)}同步</time></> : null}
        {!hasGroupModels && !catalog.synced_at ? "尚未获取到模型目录" : null}
      </p>
      {syncHint ? <p className="mt-1 text-xs text-[color:var(--muted)]">{syncHint}</p> : null}
      {catalog?.synced_at || hasGroupModels ? <>
        <p className="mt-1 text-xs text-[color:var(--muted)]">{scopeHint}具体模型能否调用，以实际请求结果为准。</p>
        {scopedModels.length > 0 ? <>
          <input type="search" aria-label="搜索该站模型" placeholder="搜索模型名称、ID 或归属" value={query} onChange={(event) => { setQuery(event.target.value); setLimit(20); }} className="mt-2 w-full rounded-[8px] border border-[color:var(--line)] bg-[color:var(--panel)] px-3 py-2 text-sm" />
          <ul className="mt-2 max-h-80 space-y-2 overflow-y-auto text-xs" aria-label="模型清单">
            {models.slice(0, limit).map((model) => <li key={model.id} className="min-w-0 rounded-[8px] border border-[color:var(--line)] px-3 py-2">
              <p className="break-words font-semibold">{model.name}{model.provider ? <span className="ml-2 font-normal text-[color:var(--muted)]">{model.provider}</span> : null}</p>
              {model.name !== model.id ? <p className="mono break-all text-[color:var(--muted)]">{model.id}</p> : null}
              {model.description ? <p className="mt-1 break-words">{model.description}</p> : null}
              {model.context_token_limit ? <p className="mt-1 text-[color:var(--muted)]">上下文 {model.context_token_limit.toLocaleString("zh-CN")} tokens</p> : null}
              {model.input_token_limit || model.output_token_limit ? <p className="mt-1 text-[color:var(--muted)]">{model.input_token_limit ? `输入上限 ${model.input_token_limit.toLocaleString("zh-CN")} tokens` : ""}{model.input_token_limit && model.output_token_limit ? " · " : ""}{model.output_token_limit ? `输出上限 ${model.output_token_limit.toLocaleString("zh-CN")} tokens` : ""}</p> : null}
              {model.capabilities.length > 0 ? <p className="mt-1 break-words text-[color:var(--muted)]">能力：{model.capabilities.join("、")}</p> : null}
            </li>)}
          </ul>
          {models.length === 0 ? <p className="mt-2 text-xs">没有匹配的模型。</p> : null}
          {models.length > limit ? <button type="button" onClick={() => setLimit((value) => value + 20)} className="mt-2 text-xs underline underline-offset-4">继续显示（已显示 {limit} / {models.length}）</button> : null}
        </> : <p className="mt-2 text-xs">{hasGroupModels ? "该分组的模型清单为空。" : "该密钥的模型清单为空。"}</p>}
      </> : null}
    </section>
  );
}
