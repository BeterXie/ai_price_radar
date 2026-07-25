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
    const response = await fetch(`${API}/api/v1/reports`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ offer_id: offerId, kind: "correction", message }),
    });
    setState(response.ok ? "sent" : response.status === 429 ? "limited" : "error");
    if (response.ok) setMessage("");
  }
  return (
    <form onSubmit={submit} className="rounded-[18px] border hairline bg-[color:var(--panel)] p-5">
      <label className="text-sm font-medium" htmlFor="report-message">发现价格、库存或分类错误？</label>
      <textarea id="report-message" value={message} onChange={(e) => setMessage(e.target.value)} className="mt-3 min-h-28 w-full rounded-[10px] border hairline bg-white p-3 text-sm outline-none focus:border-black" placeholder="请说明哪一项需要修正，并提供可核验信息。" />
      <div className="mt-3 flex items-center justify-between gap-4">
        <span className="text-xs text-black/45">不会公开你的输入内容</span>
        <button disabled={state === "sending"} className="tactile rounded-[10px] bg-[color:var(--ink)] px-4 py-2 text-sm text-white disabled:opacity-50">{state === "sending" ? "提交中" : state === "sent" ? "已提交" : "提交纠错"}</button>
      </div>
      {state === "error" && <p className="mt-2 text-sm text-[color:var(--danger)]">提交失败，请稍后再试。</p>}
      {state === "limited" && <p className="mt-2 text-sm text-[color:var(--danger)]">提交过于频繁，请稍后再试。</p>}
    </form>
  );
}
