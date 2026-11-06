"use client";

import { useState } from "react";
import { Check, ShareNetwork } from "@phosphor-icons/react";
import { buildShareUrl } from "@/lib/share-url";

export function SharePageButton({ path }: { path: string }) {
  const url = buildShareUrl(path);
  const [copiedUrl, setCopiedUrl] = useState("");
  const [fallbackUrl, setFallbackUrl] = useState("");
  const copied = copiedUrl === url;

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(url);
      setCopiedUrl(url);
      setFallbackUrl("");
    } catch {
      setCopiedUrl("");
      setFallbackUrl(url);
    }
  }

  return (
    <div className="min-w-0">
      <button type="button" onClick={copyLink} className="inline-flex min-h-11 items-center gap-1.5 text-sm text-[color:var(--muted)] transition hover:text-[color:var(--ink)]">
        {copied ? <Check size={16} aria-hidden="true" /> : <ShareNetwork size={16} aria-hidden="true" />}
        <span aria-live="polite">{copied ? "链接已复制" : "复制分享链接"}</span>
      </button>
      {fallbackUrl === url ? (
        <div className="max-w-sm text-sm">
          <p role="status">浏览器未允许复制，请选择下方链接手动复制。</p>
          <input aria-label="分享链接" readOnly value={url} onFocus={(event) => event.currentTarget.select()} className="mt-2 w-full rounded border border-[color:var(--line)] bg-[color:var(--panel)] p-2" />
        </div>
      ) : null}
    </div>
  );
}
