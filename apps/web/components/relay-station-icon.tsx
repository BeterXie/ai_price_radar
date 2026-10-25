"use client";

import { useEffect, useRef, useState } from "react";

export function RelayStationIcon({ id, name, website }: { id: number; name: string; website: string }) {
  const [attempt, setAttempt] = useState(0);
  let site = "";
  try { site = new URL(website).host; } catch { /* Only public HTTPS URLs reach this component. */ }
  const src = site ? `/api/v1/relays/${id}/icon?site=${encodeURIComponent(site)}${attempt ? `&retry=${attempt}` : ""}` : "";
  const imageRef = useRef<HTMLImageElement>(null);
  const [loadedSrc, setLoadedSrc] = useState("");
  const [failedSrc, setFailedSrc] = useState("");
  const initial = Array.from(name.trim())[0]?.toLocaleUpperCase() || "站";

  useEffect(() => {
    // Cached successes and failures can finish before hydration attaches events.
    const image = imageRef.current;
    if (image?.complete && image.currentSrc) {
      if (image.naturalWidth > 0) setLoadedSrc(src);
      else setFailedSrc(src);
    }
  }, [src]);

  useEffect(() => {
    const delays = [2000, 35000, 90000];
    if (!src || failedSrc !== src || attempt >= delays.length) return;
    const timer = window.setTimeout(() => setAttempt(attempt + 1), delays[attempt]);
    return () => window.clearTimeout(timer);
  }, [attempt, failedSrc, src]);

  return (
    <span className="relay-card-mark" aria-hidden="true">
      <span>{initial}</span>
      {src && failedSrc !== src ? (
        // Small, bounded same-origin favicons already cached by the API.
        // eslint-disable-next-line @next/next/no-img-element
        <img ref={imageRef} src={src} width={28} height={28} alt="" loading="lazy" decoding="async" referrerPolicy="no-referrer"
          className={loadedSrc === src ? "relay-site-icon is-loaded" : "relay-site-icon"}
          onLoad={() => setLoadedSrc(src)} onError={() => setFailedSrc(src)} />
      ) : null}
    </span>
  );
}
