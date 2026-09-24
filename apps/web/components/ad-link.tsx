"use client";

import type { ReactNode } from "react";

const publicApiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "";

/**
 * Outbound link for admin-configured promotions (广告栏位 / 中转站).
 *
 * Click counting is fire-and-forget: the navigation must never wait on it,
 * and a failed beacon must never block the user.
 */
export function AdLink({
  kind,
  id,
  href,
  className,
  children,
  ariaLabel,
}: {
  kind: "ads" | "relays";
  id: number;
  href: string;
  className?: string;
  children: ReactNode;
  ariaLabel?: string;
}) {
  if (!href) return <span className={className}>{children}</span>;
  const internal = href.startsWith("/");
  const handleClick = () => {
    try {
      fetch(`${publicApiBase}/api/v1/${kind}/${id}/click`, {
        method: "POST",
        credentials: "include",
        keepalive: true,
      }).catch(() => {});
    } catch {
      // Ignore beacon failures.
    }
  };
  return (
    <a
      href={href}
      onClick={handleClick}
      className={className}
      aria-label={ariaLabel}
      {...(internal ? {} : { target: "_blank", rel: "noreferrer nofollow sponsored" })}
    >
      {children}
    </a>
  );
}
