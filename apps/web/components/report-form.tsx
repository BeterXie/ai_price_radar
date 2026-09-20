"use client";

import { FormEvent, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "";
const MAX_MESSAGE_LENGTH = 2000;

export function ReportForm({
  offerId,
  productSlug,
  previewState,
}: {
  offerId?: number;
  productSlug?: string;
  previewState?: "sent" | "limited" | "error";
}) {
  const [message, setMessage] = useState("");
  const [state, setState] = useState<"idle" | "sending" | "sent" | "limited" | "invalid" | "error">(previewState || "idle");
  async function submit(event: FormEvent) {
    event.preventDefault();
    const submittedMessage = message;
    if (submittedMessage.trim().length < 10 || submittedMessage.length > MAX_MESSAGE_LENGTH) return;
    setState("sending");
    try {
      const response = await fetch(`${API}/api/v1/reports`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ offer_id: offerId, product_slug: productSlug, kind: "correction", message: submittedMessage }),
      });
      if (response.ok) {
        setState("sent");
        setMessage((current) => current === submittedMessage ? "" : current);
      } else if (response.status === 429) {
        setState("limited");
      } else if (response.status === 422) {
        setState("invalid");
      } else {
        setState("error");
      }
    } catch {
      setState("error");
    }
  }
  const canSubmit = message.trim().length >= 10 && message.length <= MAX_MESSAGE_LENGTH;
  return (
    <form onSubmit={submit} className="surface-panel p-5" data-vds-layer="evidence">
      <label className="text-sm font-medium" htmlFor="report-message">发现价格、库存或分类错误？</label>
      <textarea
        id="report-message"
        value={message}
        maxLength={MAX_MESSAGE_LENGTH}
        disabled={state === "sending"}
        onChange={(e) => { setMessage(e.target.value); setState("idle"); }}
        className="field mt-3 min-h-28 resize-y text-sm disabled:cursor-wait disabled:opacity-70"
        placeholder="请说明哪一项需要修正，并提供可核验信息。"
      />
      <div className="mt-3 flex items-center justify-between gap-4">
        <span className="text-xs text-[color:var(--muted)]">10–2000 字 · {message.length}/2000 · 提交内容不会原文公开</span>
        <button type="submit" disabled={state === "sending" || !canSubmit} className="button-primary tactile disabled:cursor-not-allowed disabled:border-[color:var(--disabled)] disabled:bg-[color:var(--disabled)]">{state === "sending" ? "提交中" : "提交纠错"}</button>
      </div>
      {state === "sent" && <p role="status" className="mt-3 rounded-[9px] bg-[color:var(--success-soft)] px-3 py-2 text-sm text-[color:var(--success)]">已收到纠错。提交内容仅用于审核，不会原文公开。</p>}
      {state === "invalid" && <p role="alert" className="mt-3 rounded-[9px] bg-[color:var(--danger-soft)] px-3 py-2 text-sm text-[color:var(--danger)]">内容未通过校验，请确认长度和关联页面后再提交。</p>}
      {state === "error" && <p role="alert" className="mt-3 rounded-[9px] bg-[color:var(--danger-soft)] px-3 py-2 text-sm text-[color:var(--danger)]">提交失败，输入已保留，请稍后重试。</p>}
      {state === "limited" && <p role="alert" className="mt-3 rounded-[9px] bg-[color:var(--warning-soft)] px-3 py-2 text-sm text-[color:var(--warning)]">提交过于频繁，输入已保留，请稍后重试。</p>}
    </form>
  );
}
