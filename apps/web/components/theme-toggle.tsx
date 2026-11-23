"use client";

import { Moon, Sun } from "@phosphor-icons/react";
import { THEME_COOKIE } from "@/lib/theme";

export function ThemeToggle() {
  function toggle() {
    const root = document.documentElement;
    const next = root.dataset.theme === "dark" ? "light" : "dark";
    root.dataset.theme = next;
    document.cookie = `${THEME_COOKIE}=${next}; Path=/; Max-Age=31536000; SameSite=Lax`;
  }

  return (
    <button type="button" className="theme-toggle" title="切换明暗模式" onClick={toggle}>
      <span className="theme-to-dark"><Moon size={19} aria-hidden="true" /><span className="sr-only">切换到深色模式</span></span>
      <span className="theme-to-light"><Sun size={19} aria-hidden="true" /><span className="sr-only">切换到浅色模式</span></span>
    </button>
  );
}
