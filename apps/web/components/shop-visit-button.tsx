"use client";

import { ArrowSquareOut } from "@phosphor-icons/react";

const publicApiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "";

export function ShopVisitButton({
  shopToken,
  sourceUrl,
}: {
  shopToken: string;
  sourceUrl: string;
}) {
  const handleClick = () => {
    try {
      fetch(`${publicApiBase}/api/v1/shops/${encodeURIComponent(shopToken)}/click`, {
        method: "POST",
        keepalive: true,
      }).catch(() => {});
    } catch {
      // Ignore network error
    }
  };

  return (
    <a
      href={sourceUrl}
      target="_blank"
      rel="noreferrer nofollow"
      onClick={handleClick}
      className="button-primary tactile"
    >
      访问原店铺 <ArrowSquareOut size={17} />
    </a>
  );
}
