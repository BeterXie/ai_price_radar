"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Megaphone, X, ArrowRight } from "@phosphor-icons/react";
import type { SiteNotice } from "@/lib/types";
import { safeInternalPath } from "@/lib/safe-url";

/**
 * Stable identity for the *version* of a notice. Admins often keep the same
 * title while updating the body or link, so dismissing must be keyed on the
 * whole content, not on a title prefix — otherwise users who closed the old
 * version would never see the update.
 */
function noticeVersionKey(notice: SiteNotice): string {
  const parts = [
    notice.badge ?? "",
    notice.title ?? "",
    notice.content ?? "",
    notice.link_url ?? "",
    notice.link_text ?? "",
  ];
  const raw = parts.join("\u0000");
  // Compact, dependency-free hash; collisions across notice versions are
  // acceptable here because a miss only re-shows the notice once.
  let hash = 5381;
  for (let index = 0; index < raw.length; index += 1) {
    hash = ((hash << 5) + hash) ^ raw.charCodeAt(index);
    hash |= 0;
  }
  return `${(hash >>> 0).toString(36)}-${raw.length}`;
}

export function SiteNoticePrompt({ notice }: { notice?: SiteNotice | null }) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (!notice || !notice.enabled || !notice.title) {
      setVisible(false);
      return;
    }
    try {
      const dismissedKey = `apr:notice:dismissed:${noticeVersionKey(notice)}`;
      if (localStorage.getItem(dismissedKey)) {
        setVisible(false);
        return;
      }
      setVisible(true);
    } catch {
      setVisible(true);
    }
  }, [notice]);

  const dismiss = () => {
    try {
      if (notice) {
        localStorage.setItem(`apr:notice:dismissed:${noticeVersionKey(notice)}`, "1");
      }
    } catch {
      // Storage might be disabled
    }
    setVisible(false);
  };

  if (!visible || !notice?.enabled || !notice?.title) return null;
  const noticeLink = safeInternalPath(notice.link_url);

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
          {noticeLink && notice.link_text && (
            <Link
              href={noticeLink}
              className="inline-flex shrink-0 items-center gap-1 font-semibold text-[color:var(--info)] hover:underline"
            >
              {notice.link_text}
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
