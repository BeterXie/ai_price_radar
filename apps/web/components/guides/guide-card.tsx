import Link from "next/link";
import { ArrowRight, BookOpenText } from "@phosphor-icons/react/ssr";

type GuideCardProps = { href: string; title: string; description: string; meta?: string };

export function GuideCard({ href, title, description, meta }: GuideCardProps) {
  return (
    <Link href={href} className="guide-card tactile group" data-vds-layer="evidence">
      <div className="guide-card-icon"><BookOpenText size={20} /></div>
      <div className="guide-card-copy">
        {meta ? <span className="pill green">{meta}</span> : null}
        <h3>{title}</h3>
        <p>{description}</p>
      </div>
      <span className="guide-card-arrow" aria-hidden="true"><ArrowRight size={17} /></span>
    </Link>
  );
}
