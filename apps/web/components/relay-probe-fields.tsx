"use client";

export type RelayProbeDraft = {
  base_url: string;
  api_key?: string;
  probe_protocol: "openai" | "anthropic" | "gemini";
  probe_model: string;
  monitor_enabled: boolean;
};

export function RelayProbeFields({ value, onChange, required = false, hasApiKey = false }: {
  value: RelayProbeDraft;
  onChange: (value: Partial<RelayProbeDraft>) => void;
  required?: boolean;
  hasApiKey?: boolean;
}) {
  return <fieldset className="grid gap-4 rounded-[10px] border border-[color:var(--line)] p-4">
    <legend className="px-2 text-sm font-semibold">接口探活与稳定性检测</legend>
    <label className="grid gap-2 text-sm">Base URL<input type="url" required={required || value.monitor_enabled} maxLength={1000} value={value.base_url} onChange={(e) => onChange({ base_url: e.target.value })} placeholder="https://api.example.com/v1" className="field text-sm"/><span className="text-xs text-[color:var(--muted)]">填写接口根地址，保留服务商要求的路径前缀；不要填写完整的 chat/completions 地址。</span></label>
    <label className="grid gap-2 text-sm">检测密钥<input type="password" autoComplete="new-password" required={(required || value.monitor_enabled) && !hasApiKey} maxLength={1000} value={value.api_key || ""} onChange={(e) => onChange({ api_key: e.target.value })} placeholder={hasApiKey ? "已加密保存，留空保留；输入新密钥可替换" : "使用专门用于检测的低额度密钥"} className="field text-sm"/></label>
    <div className="grid gap-4 sm:grid-cols-2">
      <label className="grid gap-2 text-sm">接口协议<select value={value.probe_protocol} onChange={(e) => onChange({ probe_protocol: e.target.value as RelayProbeDraft["probe_protocol"] })} className="field text-sm"><option value="openai">OpenAI 兼容接口</option><option value="anthropic">Anthropic Messages</option><option value="gemini">Gemini 原生接口</option></select></label>
      <label className="grid gap-2 text-sm">检测模型 ID<input required={required || value.monitor_enabled} maxLength={120} value={value.probe_model} onChange={(e) => onChange({ probe_model: e.target.value })} placeholder="填写此密钥有权限使用的模型 ID" className="field text-sm"/></label>
    </div>
    {!required && <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={value.monitor_enabled} onChange={(e) => onChange({ monitor_enabled: e.target.checked })}/>开启定时检测</label>}
    <p className="text-xs leading-6 text-[color:var(--muted)]">审核上线后，每小时最多发送一次简短模型请求，可能消耗少量额度。密钥加密保存，不公开展示；检测结果仅代表该密钥和模型在采样时的表现。</p>
  </fieldset>;
}
