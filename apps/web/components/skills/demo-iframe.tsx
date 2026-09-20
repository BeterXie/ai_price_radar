"use client";

import { useEffect, useRef, useState } from "react";

export function DemoIframe({
  src,
  title,
  className = "h-full w-full border-0 bg-white",
}: {
  src: string;
  title: string;
  className?: string;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [shouldLoad, setShouldLoad] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    setShouldLoad(false);
    const element = containerRef.current;
    if (!element || typeof IntersectionObserver === "undefined") {
      setShouldLoad(true);
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.some((entry) => entry.isIntersecting);
        if (visible) setLoading(true);
        setShouldLoad(visible);
      },
      { rootMargin: "300px" },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, [src]);

  return (
    <div ref={containerRef} className="relative h-full w-full bg-white">
      {shouldLoad && loading ? (
        <div className="absolute inset-0 flex items-center justify-center text-xs sm:text-sm text-neutral-400 bg-neutral-900">
          <div className="flex items-center gap-2">
            <span className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-neutral-400 border-t-transparent" />
            <span>加载动画效果中...</span>
          </div>
        </div>
      ) : null}
      {shouldLoad ? (
        <iframe
          key={src}
          src={src}
          title={title}
          sandbox="allow-scripts"
          loading="lazy"
          referrerPolicy="no-referrer"
          onLoad={() => setLoading(false)}
          onError={() => setLoading(false)}
          className={className}
        />
      ) : null}
    </div>
  );
}
