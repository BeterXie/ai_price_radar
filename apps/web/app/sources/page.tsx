import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, Globe, Stack } from "@phosphor-icons/react/ssr";
import { getMeta } from "@/lib/api";
import { JsonLd, breadcrumbJsonLd } from "@/components/structured-data";

export const dynamic = "force-dynamic";
const SITE_URL = "https://ai.pricememo.cn";
const DISABLED_SOURCES = new Set(["dujiao_next"]);
export const metadata: Metadata = { title: "来源平台", description: "AI Price Radar 收录的公开 AI 商品来源平台，包含 16688、LDXP 等平台的店铺与报价数据。", alternates: { canonical: `${SITE_URL}/sources` }, robots: { index: true, follow: true } };

export default async function SourcesPage() {
  const meta = await getMeta();
  const platforms = meta.source_platforms.filter((p) => !DISABLED_SOURCES.has(p.id));
  const canonical = `${SITE_URL}/sources`;
  const structuredData = [breadcrumbJsonLd([{ name: "首页", path: "/" }, { name: "来源平台", path: "/sources" }]), { "@context": "https://schema.org", "@type": "CollectionPage", "@id": canonical, url: canonical, name: "来源平台", description: "AI Price Radar 收录的公开 AI 商品来源平台。", isPartOf: { "@id": "https://ai.pricememo.cn/#website" }, mainEntity: { "@type": "ItemList", numberOfItems: platforms.length, itemListElement: platforms.map((platform, index) => ({ "@type": "ListItem", position: index + 1, name: platform.label, url: `${SITE_URL}/sources/${encodeURIComponent(platform.id)}` })) } }];
  return (
    <main id="main-content" className="container">
      <JsonLd data={structuredData} />
      <div className="page-content"><header className="page-intro"><span className="eyebrow">DATA SOURCES</span><h1>知道价格，<br /><span className="green-text">也知道它从哪里来。</span></h1><p>我们保留公开来源平台、店铺与原始商品链接，让每一条报价都可以回到出处核对。</p></header><section className="directory-grid source-directory">{platforms.map((platform) => <Link key={platform.id} href={`/sources/${encodeURIComponent(platform.id)}`} className="directory-card"><div className="directory-card-icon"><Globe size={21} /></div><div className="directory-card-copy"><span className="eyebrow">SOURCE PLATFORM</span><h2>{platform.label}</h2><p>来源标识 · {platform.id}</p><div className="directory-card-meta"><span><Stack size={13} />查看店铺、标准产品与公开报价</span></div></div><ArrowRight className="directory-arrow" size={18} /></Link>)}</section></div>
    </main>
  );
}
