"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Megaphone, X, ArrowRight } from "@phosphor-icons/react";
import { CURRENT_SITE_NOTICE } from "@/lib/community";

export function SiteNoticePrompt() {
  const notice = CURRENT_SITE_NOTICE;
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (!notice.enabled) return;
    try {
      const dismissedKey = `apr:notice:dismissed:${notice.id}`;
      if (localStorage.getItem(dismissedKey)) return;
      setVisible(true);
    } catch {
      setVisible(true);
    }
  }, [notice]);

  const dismiss = () => {
    try {
      localStorage.setItem(`apr:notice:dismissed:${notice.id}`, "1");
    } catch {
      // Storage might be disabled
    }
    setVisible(false);
  };

  if (!visible || !notice.enabled) return null;

  return (
    <aside
      aria-label="网站重要通知"
      className="relative z-30 border-b border-[color:var(--line-strong)] bg-gradient-to-r from-[color:var(--panel)] via-[color:var(--surface)] to-[color:var(--panel)] px-4 py-2.5 text-xs text-[color:var(--ink)] shadow-sm sm:px-6 sm:text-sm"
    >
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-3">
        <div className="flex min-w-0 flex-1 items-center gap-2 sm:gap-3">
          <span className="flex h-6 items-center gap-1.5 rounded-full bg-[color:var(--ink)] px-2.5 py-0.5 text-[0.7rem] font-medium text-white shrink-0">
            <Megaphone size={12} weight="fill" className="text-amber-400" />
            {notice.badge}
          </span>
          <span className="font-medium truncate">{notice.title}</span>
          <span className="hidden text-[color:var(--muted)] md:inline">
            — {notice.content}
          </span>
          {notice.linkUrl && notice.linkText && (
            <Link
              href={notice.linkUrl}
              className="inline-flex shrink-0 items-center gap-1 font-semibold text-[color:var(--info)] hover:underline"
            >
              {notice.linkText}
              <ArrowRight size={13} weight="bold" />
            </Link>
          )}
        </div>

        <button
          type="button"
          onClick={dismiss}
          aria-label="关闭通知"
          className="tactile -mr-1 grid h-7 w-7 shrink-0 place-items-center rounded-md text-[color:var(--muted)] transition-colors hover:bg-black/5 hover:text-[color:var(--ink)]"
        >
          <X size={15} weight="bold" />
        </button>
      </div>
    </aside>
  );
}
