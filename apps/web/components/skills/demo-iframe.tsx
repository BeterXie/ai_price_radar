"use client";

import { useEffect, useState } from "react";

export function DemoIframe({
  src,
  title,
  className = "h-full w-full border-0 bg-white",
}: {
  src: string;
  title: string;
  className?: string;
}) {
  const [htmlContent, setHtmlContent] = useState<string>("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    setLoading(true);
    fetch(src)
      .then((res) => {
        if (!res.ok) throw new Error("Failed to load demo HTML");
        return res.text();
      })
      .then((html) => {
        if (active) {
          setHtmlContent(html);
          setLoading(false);
        }
      })
      .catch(() => {
        if (active) {
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [src]);

  return (
    <div className="relative h-full w-full bg-white">
      {loading && !htmlContent ? (
        <div className="absolute inset-0 flex items-center justify-center text-xs sm:text-sm text-neutral-400 bg-neutral-900">
          <div className="flex items-center gap-2">
            <span className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-neutral-400 border-t-transparent" />
            <span>加载动画效果中...</span>
          </div>
        </div>
      ) : null}
      <iframe
        srcDoc={htmlContent || undefined}
        src={!htmlContent ? src : undefined}
        title={title}
        sandbox="allow-scripts"
        className={className}
      />
    </div>
  );
}
