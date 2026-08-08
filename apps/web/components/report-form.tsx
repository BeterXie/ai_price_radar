"use client";

import { FormEvent, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export function ReportForm({ offerId }: { offerId?: number }) {
  const [message, setMessage] = useState("");
  const [state, setState] = useState<"idle" | "sending" | "sent" | "limited" | "error">("idle");
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (message.trim().length < 10) return;
    setState("sending");
    try {
      const response = await fetch(`${API}/api/v1/reports`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ offer_id: offerId, kind: "correction", message }),
      });
      setState(response.ok ? "sent" : response.status === 429 ? "limited" : "error");
      if (response.ok) setMessage("");
    } catch {
      setState("error");
    }
  }
  const canSubmit = message.trim().length >= 10;
  return (
    <form onSubmit={submit} className="surface-panel p-5">
      <label className="text-sm font-medium" htmlFor="report-message">发现价格、库存或分类错误？</label>
      <textarea id="report-message" value={message} onChange={(e) => { setMessage(e.target.value); if (state !== "sending") setState("idle"); }} className="field mt-3 min-h-28 resize-y text-sm" placeholder="请说明哪一项需要修正，并提供可核验信息。" />
      <div className="mt-3 flex items-center justify-between gap-4">
        <span className="text-xs text-[color:var(--muted)]">至少填写 10 个字。提交内容不会原文公开</span>
        <button disabled={state === "sending" || !canSubmit} className="button-primary tactile disabled:cursor-not-allowed disabled:border-[color:var(--disabled)] disabled:bg-[color:var(--disabled)]">{state === "sending" ? "提交中" : "提交纠错"}</button>
      </div>
      {state === "sent" && <p role="status" className="mt-3 rounded-[9px] bg-[color:var(--success-soft)] px-3 py-2 text-sm text-[color:var(--success)]">已收到纠错。提交内容仅用于审核，不会原文公开。</p>}
      {state === "error" && <p role="alert" className="mt-3 rounded-[9px] bg-[color:var(--danger-soft)] px-3 py-2 text-sm text-[color:var(--danger)]">提交失败，输入已保留，请稍后重试。</p>}
      {state === "limited" && <p role="alert" className="mt-3 rounded-[9px] bg-[color:var(--warning-soft)] px-3 py-2 text-sm text-[color:var(--warning)]">提交过于频繁，输入已保留，请稍后重试。</p>}
    </form>
  );
}
