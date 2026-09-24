import { ArrowSquareOut } from "@phosphor-icons/react/ssr";
import { AdLink } from "@/components/ad-link";
import { getAdSlots } from "@/lib/api";
import type { AdPlacement, AdSlotPublic } from "@/lib/types";

/**
 * Server component that renders the live 广告栏位 for one placement.
 *
 * Renders nothing when the placement has no live slot, when ads are switched
 * off in the admin panel, or when the API is unreachable — an ad must never
 * cost a page its content. Every card carries a visible "广告 / 赞助" badge.
 */
export async function AdSlot({
  placement,
  limit = 2,
  variant = "banner",
  className = "",
}: {
  placement: AdPlacement;
  limit?: number;
  variant?: "banner" | "compact";
  className?: string;
}) {
  const { items } = await getAdSlots(placement, limit);
  if (items.length === 0) return null;
  return (
    <aside className={`ad-slot ad-slot-${variant} ${className}`.trim()} aria-label="赞助内容" data-placement={placement}>
      {items.map((item) => (
        <AdCard key={item.id} item={item} variant={variant} />
      ))}
    </aside>
  );
}

function AdCard({ item, variant }: { item: AdSlotPublic; variant: "banner" | "compact" }) {
  const external = Boolean(item.link_url) && !item.link_url.startsWith("/");
  return (
    <article className="ad-card">
      {item.image_url ? (
        <AdLink kind="ads" id={item.id} href={item.link_url} className="ad-card-media" ariaLabel={item.title}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={item.image_url} alt="" loading="lazy" decoding="async" />
        </AdLink>
      ) : null}
      <div className="ad-card-body">
        <p className="ad-card-meta">
          <span className="ad-badge">{item.badge || "广告"}</span>
          {item.sponsor_name ? <span className="truncate">{item.sponsor_name}</span> : null}
        </p>
        <h3 className="ad-card-title">
          <AdLink kind="ads" id={item.id} href={item.link_url}>{item.title}</AdLink>
        </h3>
        {item.description && variant === "banner" ? <p className="ad-card-desc">{item.description}</p> : null}
      </div>
      {item.link_url ? (
        <AdLink kind="ads" id={item.id} href={item.link_url} className="button-secondary tactile ad-card-cta">
          {item.cta_text || "了解详情"}
          {external ? <ArrowSquareOut size={15} /> : null}
        </AdLink>
      ) : null}
    </article>
  );
}
