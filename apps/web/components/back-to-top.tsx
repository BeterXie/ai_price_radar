"use client";

import { useEffect, useState } from "react";
import { ArrowUp } from "@phosphor-icons/react";

export function BackToTop() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const updateVisibility = () => setVisible(window.scrollY > 640);
    updateVisibility();
    window.addEventListener("scroll", updateVisibility, { passive: true });
    return () => window.removeEventListener("scroll", updateVisibility);
  }, []);

  if (!visible) return null;

  return (
    <button
      type="button"
      onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
      aria-label="回到页面顶部"
      title="回到顶部"
      className="tactile fixed right-5 bottom-5 z-40 grid h-11 w-11 place-items-center rounded-full bg-[color:var(--ink)] text-white shadow-[0_10px_30px_rgba(18,19,15,.22)] hover:bg-[color:var(--accent)] hover:text-[color:var(--accent-ink)] md:right-8 md:bottom-8"
    >
      <ArrowUp size={20} weight="bold" />
    </button>
  );
}
