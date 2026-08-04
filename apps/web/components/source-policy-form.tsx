"use client";

import { useState } from "react";
import { normalizePublicHttpsUrl } from "@/lib/source-policy";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export function SourcePolicyForm({ requestType }: { requestType: "opt_out" | "correction" | "ownership" }) {
  const [sourceUrl, setSourceUrl] = useState("");
  const [email, setEmail] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [submitted, setSubmitted] = useState(false);

  async function submit() {
    setError("");
    if (!normalizePublicHttpsUrl(sourceUrl)) {
      setError("请输入有效的公开 HTTPS 来源地址。");
      return;
    }
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.trim())) {
      setError("请输入有效的联系邮箱。");
      return;
    }
    const response = await fetch(`${API}/api/v1/source-policy/requests`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source_url: sourceUrl.trim(),
        request_type: requestType,
        requester_email: email.trim(),
        reason: reason.trim(),
      }),
    });
    if (!response.ok) {
      setError("提交失败，请稍后重试或联系管理员。");
      return;
    }
    setSubmitted(true);
  }

  if (submitted) {
    return (
      <div className="rounded-[14px] border hairline bg-[color:var(--panel)] p-6">
        <p className="font-medium">已收到你的请求。</p>
        <p className="mt-2 text-sm leading-6 text-black/60">
          退出收录请求会立即对该来源暂停采集（最长 7 天等待核实）；管理员处理完成后会邮件通知。
        </p>
      </div>
    );
  }

  return (
    <form
      className="grid gap-4 rounded-[14px] border hairline bg-[color:var(--panel)] p-6"
      onSubmit={(event) => {
        event.preventDefault();
        void submit();
      }}
    >
      <label className="text-sm font-medium">
        来源地址
        <input
          value={sourceUrl}
          onChange={(event) => setSourceUrl(event.target.value)}
          placeholder="https://example.com/shop/TOKEN"
          className="mt-1.5 w-full rounded-[10px] border hairline bg-white px-3 py-2 text-sm text-black"
        />
      </label>
      <label className="text-sm font-medium">
        联系邮箱
        <input
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder="owner@example.com"
          type="email"
          className="mt-1.5 w-full rounded-[10px] border hairline bg-white px-3 py-2 text-sm text-black"
        />
      </label>
      <label className="text-sm font-medium">
        说明 <span className="font-normal text-black/50">选填</span>
        <textarea
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          rows={3}
          className="mt-1.5 w-full rounded-[10px] border hairline bg-white px-3 py-2 text-sm text-black"
        />
      </label>
      {error && <p className="rounded-[10px] bg-[#f2d8d2] p-3 text-sm text-[color:var(--danger)]">{error}</p>}
      <button type="submit" className="tactile rounded-[10px] bg-[color:var(--ink)] px-5 py-3 text-sm text-white">
        提交请求
      </button>
    </form>
  );
}
