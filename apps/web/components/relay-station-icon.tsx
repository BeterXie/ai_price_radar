"use client";

import { useEffect, useState } from "react";

export function RelayStationIcon({ id, name, website }: { id: number; name: string; website: string }) {
  const [attempt, setAttempt] = useState(0);
  const src = website ? `/api/v1/relays/${id}/icon${attempt ? `?retry=${attempt}` : ""}` : "";
  const [loadedSrc, setLoadedSrc] = useState("");
  const [failedSrc, setFailedSrc] = useState("");
  const initial = Array.from(name.trim())[0]?.toLocaleUpperCase() || "站";

  useEffect(() => {
    if (!src || failedSrc !== src || attempt >= 2) return;
    const timer = window.setTimeout(() => setAttempt(attempt + 1), 2000 * (attempt + 1));
    return () => window.clearTimeout(timer);
  }, [attempt, failedSrc, src]);

  return (
    <span className="relay-card-mark" aria-hidden="true">
      <span>{initial}</span>
      {src && failedSrc !== src ? (
        // Small, bounded same-origin favicons already cached by the API.
        // eslint-disable-next-line @next/next/no-img-element
        <img src={src} width={28} height={28} alt="" loading="lazy" decoding="async" referrerPolicy="no-referrer"
          className={loadedSrc === src ? "relay-site-icon is-loaded" : "relay-site-icon"}
          onLoad={() => setLoadedSrc(src)} onError={() => setFailedSrc(src)} />
      ) : null}
    </span>
  );
}
