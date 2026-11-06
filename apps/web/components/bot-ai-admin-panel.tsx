"use client";

import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "";
type AISettings = {
  enabled: boolean;
  base_url: string;
  model: string;
  api_style: "chat_completions" | "responses";
  api_key_configured: boolean;
};
const inputClass = "mt-2 min-h-11 w-full rounded-[10px] border border-[color:var(--line-strong)] bg-[color:var(--surface)] px-3 text-sm text-[color:var(--ink)] focus:border-[color:var(--ink)] focus:outline-none disabled:opacity-60";

function errorMessage(body: { detail?: unknown }, fallback: string): string {
  if (typeof body.detail === "string") return body.detail;
  if (Array.isArray(body.detail)) {
    const messages = body.detail.map((item) => typeof item?.msg === "string" ? item.msg : "").filter(Boolean);
    if (messages.length) return messages.join("；");
  }
  return fallback;
}

export function BotAIAdminPanel({ adminKey, botEnabled }: { adminKey: string; botEnabled: boolean }) {
  const [saved, setSaved] = useState<AISettings | null>(null);
  const [form, setForm] = useState<AISettings | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [clearKey, setClearKey] = useState(false);
  const [loading, setLoading] = useState(true);
  const [reload, setReload] = useState(0);
  const [busy, setBusy] = useState<"save" | "test" | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    fetch(`${API}/api/v1/admin/bot-ai`, { headers: { "X-Admin-Key": adminKey }, cache: "no-store", signal: controller.signal })
      .then(async (response) => {
        const body = await response.json();
        if (!response.ok) throw new Error(errorMessage(body, "AI 配置读取失败，请重试。"));
        if (!controller.signal.aborted) {
          setSaved(body);
          setForm(body);
          setApiKey("");
          setClearKey(false);
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) setError("AI 配置读取失败，请重新加载后再修改。");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [adminKey, reload]);

  function change(patch: Partial<AISettings>) {
    setForm((current) => current ? { ...current, ...patch } : current);
    setMessage("");
    setError("");
  }

  async function submit(action: "save" | "test") {
    if (!form || loading || busy) return;
    setError("");
    setMessage("");
    const replacing = apiKey.trim();
    const hasKey = Boolean(replacing || (form.api_key_configured && !clearKey));
    if ((form.enabled || action === "test") && (!form.base_url.trim() || !form.model.trim() || !hasKey)) {
      setError("请填写接口地址、模型和密钥后再启用或测试。");
      return;
    }
    if (saved?.api_key_configured && form.base_url.trim().replace(/\/+$/, "") !== saved.base_url && !replacing && !clearKey) {
      setError("更换接口地址时，请同时填写该接口的密钥，或清除旧密钥。");
      return;
    }
    setBusy(action);
    try {
      const response = await fetch(`${API}/api/v1/admin/bot-ai${action === "test" ? "/test" : ""}`, {
        method: action === "test" ? "POST" : "PUT",
        headers: { "X-Admin-Key": adminKey, "Content-Type": "application/json" },
        body: JSON.stringify({
          enabled: form.enabled, base_url: form.base_url.trim(), model: form.model.trim(), api_style: form.api_style,
          api_key: replacing || null, clear_api_key: clearKey,
        }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(errorMessage(body, action === "test" ? "连接测试失败，请重试。" : "保存失败，请重试。"));
      if (action === "save") {
        setSaved(body);
        setForm(body);
        setApiKey("");
        setClearKey(false);
        setMessage(body.enabled ? "已保存，下一条 QQ 查询将使用新配置。" : "已保存，AI 已关闭，机器人使用规则查价。");
      } else {
        setMessage(body.message);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "网络请求失败，请重试。");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="border-t border-[color:var(--line-strong)] p-5">
      <div className="flex flex-wrap items-center gap-3">
        <h3 className="text-sm font-semibold text-[color:var(--ink)]">AI 价格助手</h3>
        {saved && <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${saved.enabled ? "bg-[color:var(--success-soft)] text-[color:var(--success)]" : "bg-[color:var(--subtle)] text-[color:var(--muted)]"}`}>{saved.enabled ? "已启用" : "未启用"}</span>}
      </div>
      <p className="mt-1.5 text-xs leading-5 text-[color:var(--muted)]">自然语言查价、比较商品、解释账号与代充。保存后生效，无需重启。</p>
      {loading && <p role="status" className="mt-4 text-sm text-[color:var(--muted)]">正在读取 AI 配置…</p>}
      {!loading && !form && <button type="button" onClick={() => setReload((value) => value + 1)} className="mt-4 text-sm underline underline-offset-4">重新加载 AI 配置</button>}
      {form && (
        <form onSubmit={(event) => { event.preventDefault(); void submit("save"); }} className="mt-5">
          <fieldset disabled={loading || busy !== null}>
            <label className="flex min-h-10 cursor-pointer items-center gap-3 text-sm font-medium">
              <input type="checkbox" checked={form.enabled} onChange={(event) => change({ enabled: event.target.checked })} className="h-4 w-4 accent-[color:var(--ink)]" />
              启用 AI 价格助手
            </label>
            {!botEnabled && <p className="mt-1 text-xs text-[color:var(--muted)]">机器人总开关已关闭。配置可保存，开启上方机器人服务后才会回复 QQ 消息。</p>}
            <div className="mt-4 grid gap-5 md:grid-cols-2">
              <label className="text-sm font-medium md:col-span-2">
                API 接口地址
                <input type="url" value={form.base_url} onChange={(event) => change({ base_url: event.target.value })} maxLength={500} placeholder="https://api.example.com/v1" autoComplete="off" spellCheck={false} className={inputClass} />
                <span className="mt-1.5 block text-xs font-normal leading-5 text-[color:var(--muted)]">填写服务商的 API 基础地址，通常以 /v1 结尾。</span>
              </label>
              <label className="text-sm font-medium">
                模型名称
                <input value={form.model} onChange={(event) => change({ model: event.target.value })} maxLength={150} placeholder="填写服务商提供的模型名称" autoComplete="off" spellCheck={false} className={inputClass} />
              </label>
              <label className="text-sm font-medium">
                接口格式
                <select value={form.api_style} onChange={(event) => change({ api_style: event.target.value as AISettings["api_style"] })} className={inputClass}>
                  <option value="chat_completions">Chat Completions（兼容接口）</option>
                  <option value="responses">Responses</option>
                </select>
              </label>
              <label className="text-sm font-medium md:col-span-2">
                API 密钥
                <input type="password" value={apiKey} disabled={clearKey} onChange={(event) => { setApiKey(event.target.value); setMessage(""); setError(""); }} maxLength={4096} placeholder={form.api_key_configured ? "已配置，留空保留；填写新密钥可替换" : "填写 API 密钥"} autoComplete="new-password" spellCheck={false} className={inputClass} />
                <span className="mt-1.5 block text-xs font-normal leading-5 text-[color:var(--muted)]">密钥加密保存，不回显。只更换模型时可留空。</span>
              </label>
            </div>
            {form.api_key_configured && <label className="mt-3 flex min-h-10 cursor-pointer items-center gap-3 text-xs text-[color:var(--muted)]"><input type="checkbox" checked={clearKey} onChange={(event) => { setClearKey(event.target.checked); setApiKey(""); setMessage(""); setError(""); }} className="h-4 w-4 accent-[color:var(--ink)]" />清除已保存密钥（需关闭 AI）</label>}
            <div className="mt-5 flex flex-wrap gap-3">
              <button type="submit" className="tactile min-h-11 rounded-[10px] bg-[color:var(--ink)] px-5 text-sm font-semibold text-white hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50">{busy === "save" ? "正在保存…" : "保存并应用"}</button>
              <button type="button" onClick={() => void submit("test")} className="tactile min-h-11 rounded-[10px] border border-[color:var(--line-strong)] px-5 text-sm font-medium hover:bg-[color:var(--subtle)] disabled:cursor-not-allowed disabled:opacity-50">{busy === "test" ? "正在测试…" : "测试连接"}</button>
            </div>
            <p className="mt-2 text-xs leading-5 text-[color:var(--muted)]">测试会调用一次所填模型，不保存配置。</p>
          </fieldset>
        </form>
      )}
      {error && <p role="alert" className="mt-4 text-sm text-[color:var(--danger)]">{error}</p>}
      {message && <p role="status" className="mt-4 text-sm text-[color:var(--success)]">{message}</p>}
    </div>
  );
}
