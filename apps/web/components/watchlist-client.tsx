"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { BellRinging, CheckCircle, Copy, Rss, Trash } from "@phosphor-icons/react";
import type { CatalogResponse, ProductCard } from "@/lib/types";
import { money, relativeTime } from "@/lib/format";
import { readWatchlist, WATCHLIST_EVENT, type WatchItem, writeWatchlist } from "@/components/watch-button";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export function WatchlistClient() {
  const [items, setItems] = useState<WatchItem[]>([]);
  const [products, setProducts] = useState<Record<string, ProductCard>>({});
  const [copied, setCopied] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const sync = () => setItems(readWatchlist());
    sync();
    window.addEventListener(WATCHLIST_EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(WATCHLIST_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, []);

  useEffect(() => {
    let active = true;
    async function load() {
      setLoading(true);
      const results = await Promise.all(items.map(async (item) => {
        try {
          const response = await fetch(`${API}/api/v1/products?product=${encodeURIComponent(item.slug)}&sort=quality`, { cache: "no-store" });
          if (!response.ok) return null;
          const data = await response.json() as CatalogResponse;
          return data.items[0] || null;
        } catch {
          return null;
        }
      }));
      if (active) {
        setProducts(Object.fromEntries(results.filter((value): value is ProductCard => Boolean(value)).map((product) => [product.slug, product])));
        setLoading(false);
      }
    }
    void load();
    return () => { active = false; };
  }, [items]);

  const feedUrl = useMemo(() => {
    const targets = items.map((item) => `${item.slug}${item.threshold ? `:${item.threshold}` : ""}`).join(",");
    return targets ? `${API}/api/v1/watch.atom?targets=${encodeURIComponent(targets)}` : "";
  }, [items]);

  function updateThreshold(slug: string, threshold: string) {
    const normalized = threshold.replace(/[^0-9.]/g, "").slice(0, 12);
    const next = items.map((item) => item.slug === slug ? { ...item, threshold: normalized } : item);
    setItems(next);
    writeWatchlist(next);
  }

  function remove(slug: string) {
    writeWatchlist(items.filter((item) => item.slug !== slug));
  }

  async function copyFeed() {
    if (!feedUrl) return;
    await navigator.clipboard.writeText(feedUrl);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  }

  if (!items.length) {
    return (
      <div className="empty-state">
        <BellRinging className="mx-auto" size={34} />
        <h2 className="mt-4 text-2xl font-semibold">关注清单还是空的</h2>
        <p className="mt-3 text-sm leading-6 text-black/50">进入任意商品页，点击“加入关注清单”。关注数据只保存在当前浏览器。</p>
        <Link href="/products" className="button-primary mt-6">浏览报价目录</Link>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <section className="data-table-frame overflow-hidden border border-[color:var(--line-strong)] bg-[color:var(--panel)]">
        <div className="grid gap-3 border-b border-[color:var(--line-strong)] bg-[color:var(--subtle)] px-5 py-4 text-xs text-[color:var(--muted)] md:grid-cols-[1fr_150px_150px_110px]">
          <span>商品与当前状态</span><span>近期有货最低价</span><span>提醒目标价</span><span>操作</span>
        </div>
        <div className="divide-y divide-[color:var(--line)]">
          {items.map((item) => {
            const product = products[item.slug];
            const current = product?.lowest_price ? Number(product.lowest_price) : null;
            const threshold = item.threshold ? Number(item.threshold) : null;
            const reached = Boolean(product && product.in_stock_count > 0 && (threshold === null || (current !== null && current <= threshold)));
            return (
              <div key={item.slug} className="grid gap-4 px-5 py-5 md:grid-cols-[1fr_150px_150px_110px] md:items-center">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Link href={`/products/${encodeURIComponent(item.slug)}`} className="font-semibold hover:underline">{product?.display_name || item.name}</Link>
                    {reached && <span className="status-pill status-success !py-1 !text-[10px]"><CheckCircle size={12} weight="fill" />达到条件</span>}
                  </div>
                  <p className="mt-2 text-xs text-black/45">{product ? `${product.in_stock_count} 条有货 · ${product.trusted_offer_count} 条纳入统计 · ${relativeTime(product.last_updated_at)}更新` : loading ? "正在加载…" : "报价暂时无法加载"}</p>
                </div>
                <div className="font-semibold">{product ? money(product.lowest_price, product.price_currency) : "暂无"}</div>
                <label className="text-xs text-black/45">
                  <span className="sr-only">{item.name} 提醒目标价</span>
                  <span className="flex items-center rounded-[9px] border border-[color:var(--line-strong)] bg-[color:var(--panel)] px-3"><span>{product?.price_currency || item.currency || "CNY"}</span><input value={item.threshold} onChange={(event) => updateThreshold(item.slug, event.target.value)} inputMode="decimal" placeholder="不限" className="w-full bg-transparent py-2.5 pl-1 outline-none" /></span>
                </label>
                <button type="button" onClick={() => remove(item.slug)} className="button-tertiary !justify-start !px-0 text-[color:var(--danger)]"><Trash size={16} />移除</button>
              </div>
            );
          })}
        </div>
      </section>

      <section className="surface-subtle p-6">
        <div className="flex items-start gap-3"><Rss className="mt-1 shrink-0" size={24} /><div><h2 className="text-xl font-semibold">订阅价格与补货更新</h2><p className="mt-2 max-w-3xl text-sm leading-6 text-black/55">把下方链接添加到支持 Atom/RSS 的阅读器。价格、库存或更新时间变化时，阅读器会出现新条目；本站不会发送消息或邮件，服务端也不保存邮箱、账号或关注清单。</p></div></div>
        <div className="mt-5 flex flex-col gap-3 sm:flex-row">
          <input readOnly value={feedUrl} aria-label="Atom Feed 地址" className="field min-w-0 flex-1 text-xs" />
          <button type="button" onClick={copyFeed} className="button-primary tactile"><Copy size={17} />{copied ? "已复制" : "复制订阅地址"}</button>
        </div>
      </section>
    </div>
  );
}
