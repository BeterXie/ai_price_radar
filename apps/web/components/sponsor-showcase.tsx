import Link from "next/link";
import { getAdSlots } from "@/lib/api";
import { SponsorCard } from "@/components/sponsor-card";

export async function SponsorShowcase() {
  const { items } = await getAdSlots("home_hero", 6);
  if (!items.length) return null;
  return (
    <section className="home-sponsors shell" aria-labelledby="home-sponsors-title" data-placement="home_hero">
      <div className="home-section-heading">
        <h2 id="home-sponsors-title">赞助伙伴</h2>
        <Link href="/relays" className="text-action">中转站目录 <span aria-hidden="true">↗</span></Link>
      </div>
      <div className="sponsor-grid" data-count={items.length}>
        {items.map((item, index) => <SponsorCard key={item.id} item={item} primary={index === 0} />)}
      </div>
    </section>
  );
}
