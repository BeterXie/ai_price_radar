"use client";

import { useEffect, useRef, type ReactNode } from "react";

export function CatalogScrollNav({ children, className, label, activeKey }: {
  children: ReactNode;
  className: string;
  label: string;
  activeKey: string;
}) {
  const ref = useRef<HTMLElement>(null);

  useEffect(() => {
    const row = ref.current;
    if (!row) return;
    const revealSelection = () => {
      if (!row.clientWidth || row.scrollWidth <= row.clientWidth) return;
      const active = row.querySelector<HTMLElement>('[aria-current="page"]');
      if (!active) return;
      const bounds = row.getBoundingClientRect();
      const selected = active.getBoundingClientRect();
      // Scroll only the tab strip; the product list must keep its vertical position.
      if (selected.left < bounds.left) row.scrollLeft += selected.left - bounds.left;
      else if (selected.right > bounds.right) row.scrollLeft += selected.right - bounds.right;
    };
    revealSelection();
    const observer = new ResizeObserver(revealSelection);
    observer.observe(row);
    return () => observer.disconnect();
  }, [activeKey]);

  return <nav ref={ref} className={className} aria-label={label}>{children}</nav>;
}
