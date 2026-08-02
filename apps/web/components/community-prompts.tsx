"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import { Coffee, GithubLogo, Heart, X } from "@phosphor-icons/react";
import {
  GITHUB_REPOSITORY_URL,
  SUPPORT_AVAILABLE,
  SUPPORT_METHODS,
} from "@/lib/community";

type PromptKind = "github" | "support";

const DAY = 24 * 60 * 60 * 1000;
const storageKeys = {
  sessionStarted: "apr:community:session-started",
  sessionPromptShown: "apr:community:prompt-shown",
  sessionCount: "apr:community:session-count",
  pageViews: "apr:community:page-views",
  lastPromptAt: "apr:community:last-prompt-at",
  githubUntil: "apr:community:github-until",
  supportUntil: "apr:community:support-until",
};

function storedNumber(storage: Storage, key: string) {
  const value = Number(storage.getItem(key) || "0");
  return Number.isFinite(value) ? value : 0;
}

function excludedPath(pathname: string) {
  return pathname.startsWith("/admin") || pathname.startsWith("/shops/submit");
}

export function CommunityPrompts() {
  const pathname = usePathname();
  const [prompt, setPrompt] = useState<PromptKind | null>(null);
  const [supportOpen, setSupportOpen] = useState(false);
  const [activeMethodId, setActiveMethodId] = useState(SUPPORT_METHODS[0]?.id || "wechat");
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const modalRootRef = useRef<HTMLDivElement>(null);

  const rememberPrompt = useCallback(() => {
    try {
      sessionStorage.setItem(storageKeys.sessionPromptShown, "1");
      localStorage.setItem(storageKeys.lastPromptAt, String(Date.now()));
    } catch {
      // Storage may be unavailable in strict privacy modes. The UI still works.
    }
  }, []);

  const snooze = useCallback((kind: PromptKind, days: number) => {
    try {
      const key = kind === "github" ? storageKeys.githubUntil : storageKeys.supportUntil;
      localStorage.setItem(key, String(Date.now() + days * DAY));
      localStorage.setItem(storageKeys.lastPromptAt, String(Date.now()));
    } catch {
      // Closing the prompt must never depend on storage access.
    }
  }, []);

  const dismissPrompt = useCallback((kind: PromptKind, days: number) => {
    snooze(kind, days);
    setPrompt(null);
  }, [snooze]);

  const openSupport = useCallback(() => {
    if (!SUPPORT_AVAILABLE) return;
    rememberPrompt();
    setPrompt(null);
    setSupportOpen(true);
  }, [rememberPrompt]);

  const closeSupport = useCallback(() => {
    snooze("support", 30);
    setSupportOpen(false);
  }, [snooze]);

  useEffect(() => {
    if (excludedPath(pathname)) {
      setPrompt(null);
      return;
    }

    try {
      if (!sessionStorage.getItem(storageKeys.sessionStarted)) {
        sessionStorage.setItem(storageKeys.sessionStarted, "1");
        localStorage.setItem(
          storageKeys.sessionCount,
          String(storedNumber(localStorage, storageKeys.sessionCount) + 1),
        );
      }

      const pageKey = `apr:community:viewed:${pathname}`;
      if (!sessionStorage.getItem(pageKey)) {
        sessionStorage.setItem(pageKey, "1");
        localStorage.setItem(
          storageKeys.pageViews,
          String(storedNumber(localStorage, storageKeys.pageViews) + 1),
        );
      }

      if (sessionStorage.getItem(storageKeys.sessionPromptShown)) return;

      const now = Date.now();
      if (now - storedNumber(localStorage, storageKeys.lastPromptAt) < 7 * DAY) return;

      const sessions = storedNumber(localStorage, storageKeys.sessionCount);
      const pageViews = storedNumber(localStorage, storageKeys.pageViews);
      const supportEligible =
        SUPPORT_AVAILABLE &&
        sessions >= 3 &&
        now >= storedNumber(localStorage, storageKeys.supportUntil);
      const githubEligible =
        (sessions >= 2 || pageViews >= 2) &&
        now >= storedNumber(localStorage, storageKeys.githubUntil);
      const nextPrompt: PromptKind | null = supportEligible ? "support" : githubEligible ? "github" : null;
      if (!nextPrompt) return;

      const timer = window.setTimeout(() => {
        rememberPrompt();
        setPrompt(nextPrompt);
      }, nextPrompt === "support" ? 60_000 : 45_000);
      return () => window.clearTimeout(timer);
    } catch {
      return;
    }
  }, [pathname, rememberPrompt]);

  useEffect(() => {
    if (!SUPPORT_AVAILABLE) return;
    const openFromHash = () => {
      if (window.location.hash !== "#support-author") return;
      rememberPrompt();
      setPrompt(null);
      setSupportOpen(true);
      window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}`);
    };
    openFromHash();
    window.addEventListener("hashchange", openFromHash);
    return () => window.removeEventListener("hashchange", openFromHash);
  }, [rememberPrompt]);

  useEffect(() => {
    if (!supportOpen) return;
    const previouslyFocused = document.activeElement as HTMLElement | null;
    const originalOverflow = document.body.style.overflow;
    const inertedSiblings = Array.from(document.body.children)
      .filter((element): element is HTMLElement => element instanceof HTMLElement && element !== modalRootRef.current)
      .map((element) => ({ element, wasInert: element.hasAttribute("inert") }));
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") closeSupport();
    };
    document.body.style.overflow = "hidden";
    inertedSiblings.forEach(({ element }) => element.setAttribute("inert", ""));
    document.addEventListener("keydown", onKeyDown);
    closeButtonRef.current?.focus();
    return () => {
      document.body.style.overflow = originalOverflow;
      inertedSiblings.forEach(({ element, wasInert }) => {
        if (!wasInert) element.removeAttribute("inert");
      });
      document.removeEventListener("keydown", onKeyDown);
      previouslyFocused?.focus();
    };
  }, [closeSupport, supportOpen]);

  const activeMethod = SUPPORT_METHODS.find((method) => method.id === activeMethodId) || SUPPORT_METHODS[0];

  return (
    <>
      {prompt && (
        <aside
          aria-label={prompt === "github" ? "开源项目提示" : "支持作者提示"}
          className="fixed inset-x-4 bottom-20 z-40 rounded-[18px] border border-black bg-[color:var(--panel)] p-5 shadow-[0_20px_50px_rgba(18,19,15,.18)] md:right-auto md:bottom-8 md:left-8 md:w-[420px]"
        >
          <div className="flex items-start gap-4">
            <div className="grid h-11 w-11 shrink-0 place-items-center rounded-[10px] bg-[color:var(--ink)] text-white">
              {prompt === "github" ? <GithubLogo size={23} weight="fill" /> : <Coffee size={23} weight="bold" />}
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-start justify-between gap-3">
                <h2 className="text-lg font-semibold tracking-[-.03em]">
                  {prompt === "github" ? "觉得网站有用？" : "这个工具帮到你了吗？"}
                </h2>
                <button
                  type="button"
                  onClick={() => dismissPrompt(prompt, prompt === "github" ? 14 : 30)}
                  aria-label="关闭提示"
                  className="tactile grid h-9 w-9 shrink-0 place-items-center rounded-[10px] border hairline"
                >
                  <X size={18} />
                </button>
              </div>
              <p className="mt-2 text-sm leading-6 text-black/60">
                {prompt === "github"
                  ? "AI Price Radar 已在 GitHub 开源。欢迎查看代码、提交建议，顺手点个 Star。"
                  : "开发、服务器和数据维护需要持续投入。你可以自愿请作者喝杯咖啡。"}
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                {prompt === "github" ? (
                  <a
                    href={GITHUB_REPOSITORY_URL}
                    target="_blank"
                    rel="noreferrer"
                    onClick={() => dismissPrompt("github", 30)}
                    className="tactile rounded-[10px] bg-[color:var(--ink)] px-4 py-2.5 text-sm font-medium text-white"
                  >
                    去 GitHub 点 Star
                  </a>
                ) : (
                  <button
                    type="button"
                    onClick={openSupport}
                    className="tactile rounded-[10px] bg-[color:var(--ink)] px-4 py-2.5 text-sm font-medium text-white"
                  >
                    支持作者
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => dismissPrompt(prompt, prompt === "github" ? 14 : 30)}
                  className="tactile rounded-[10px] border border-black px-4 py-2.5 text-sm"
                >
                  稍后再说
                </button>
              </div>
            </div>
          </div>
        </aside>
      )}

      {supportOpen && activeMethod && (
        <div
          ref={modalRootRef}
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) closeSupport();
          }}
          className="fixed inset-0 z-[60] grid place-items-center bg-black/50 p-4"
        >
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby="support-dialog-title"
            aria-describedby="support-dialog-description"
            className="max-h-[calc(100dvh-32px)] w-full max-w-[620px] overflow-y-auto rounded-[18px] border border-black bg-[color:var(--panel)] shadow-[0_28px_80px_rgba(18,19,15,.28)]"
          >
            <header className="flex items-start justify-between gap-4 border-b hairline p-5 sm:p-6">
              <div>
                <div className="flex items-center gap-2 text-sm font-medium text-black/55">
                  <Heart size={18} weight="fill" />支持 AI Price Radar
                </div>
                <h2 id="support-dialog-title" className="mt-2 text-2xl font-semibold tracking-[-.04em]">请作者喝杯咖啡</h2>
                <p id="support-dialog-description" className="mt-2 max-w-lg text-sm leading-6 text-black/60">
                  完全自愿，不影响任何功能使用。请核对支付页面信息，金额由你决定。
                </p>
              </div>
              <button
                ref={closeButtonRef}
                type="button"
                onClick={closeSupport}
                aria-label="关闭支持作者窗口"
                className="tactile grid h-10 w-10 shrink-0 place-items-center rounded-[10px] border hairline"
              >
                <X size={19} />
              </button>
            </header>

            <div className="grid gap-6 p-5 sm:grid-cols-[1fr_260px] sm:p-6">
              <div>
                <p className="text-sm font-medium">选择支付方式</p>
                <div className="mt-3 grid gap-2">
                  {SUPPORT_METHODS.map((method) => (
                    <button
                      key={method.id}
                      type="button"
                      onClick={() => setActiveMethodId(method.id)}
                      aria-pressed={activeMethod.id === method.id}
                      className={`tactile rounded-[10px] border px-4 py-3 text-left text-sm font-medium ${
                        activeMethod.id === method.id
                          ? "border-[color:var(--ink)] bg-[color:var(--ink)] text-white"
                          : "hairline bg-white text-[color:var(--ink)]"
                      }`}
                    >
                      {method.label}
                    </button>
                  ))}
                </div>
                <div className="mt-5 rounded-[10px] border hairline bg-white p-4 text-sm leading-6">
                  <p className="text-black/55">支付前请核对支付页面信息。本站不会记录你的支付信息。</p>
                </div>
              </div>

              <div className="flex flex-col items-center rounded-[10px] border hairline bg-white p-4 text-center">
                <img
                  src={activeMethod.qrUrl}
                  alt={`${activeMethod.label}支持作者二维码`}
                  width={228}
                  height={228}
                  className="aspect-square w-full max-w-[228px] object-contain"
                />
                <p className="mt-3 text-sm font-medium">使用{activeMethod.label}扫码</p>
                <p className="mt-1 text-xs leading-5 text-black/50">不预设金额，谢谢你的支持。</p>
              </div>
            </div>
          </section>
        </div>
      )}
    </>
  );
}
