import { AdLink } from "@/components/ad-link";
import type { AdSlotPublic } from "@/lib/types";

export function SponsorCard({ item, variant = "showcase", primary = false }: {
  item: AdSlotPublic;
  variant?: "showcase" | "banner" | "inline";
  primary?: boolean;
}) {
  const name = item.sponsor_name || item.title;
  const rateTitle = item.title.match(/^(.*?)\s+(\d[\d.–-]*[x×])$/i);
  return (
    <article className={`sponsor-card sponsor-${variant}${primary ? " sponsor-primary" : ""}`} data-ad-id={item.id} data-sponsor={item.sponsor_name.toLowerCase()}>
      <div className="sponsor-identity">
        <span className="sponsor-logo" aria-hidden="true">
          {item.image_url ? <img src={item.image_url} alt="" width={40} height={40} loading="lazy" decoding="async" /> : name.slice(0, 1)}
        </span>
        <AdLink kind="ads" id={item.id} href={item.link_url} className="sponsor-name">{name}</AdLink>
        <span className="sponsor-disclosure">赞助</span>
      </div>
      <div className="sponsor-copy">
        {variant === "inline" ? <p title={item.title}>{item.title}</p> : <>
          <h3><AdLink kind="ads" id={item.id} href={item.link_url}>{rateTitle ? <>{rateTitle[1]} <span className="sponsor-rate">{rateTitle[2]}</span></> : item.title}</AdLink></h3>
          {item.description ? <p>{item.description}</p> : null}
        </>}
      </div>
      {variant === "showcase" && primary && item.image_url ? <img className="sponsor-watermark" src={item.image_url} alt="" aria-hidden="true" loading="lazy" /> : null}
      <AdLink kind="ads" id={item.id} href={item.link_url} className="sponsor-cta" ariaLabel={`${item.cta_text || "了解详情"} · ${name}`}>
        {item.cta_text || "了解详情"}<span aria-hidden="true">↗</span>
      </AdLink>
    </article>
  );
}
