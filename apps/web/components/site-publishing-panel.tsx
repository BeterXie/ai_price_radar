"use client";

import { useEffect, useState } from "react";
import { BRANDS, type SiteId } from "@/lib/brands";
import type { Article, ArticlePage, SiteSettings } from "@/lib/site-content";
import { MarkdownView } from "@/components/skills/markdown-view";

type Props = { apiBase: string; headers: Record<string, string> };
type ArticleDraft = Pick<Article, "slug" | "title" | "summary" | "category" | "author" | "seo_title" | "seo_description" | "status"> & { markdown: string };
type Publication = { tagline: string; description: string; link_url: string; sort_order: number; is_enabled: boolean; is_sponsored: boolean };
type Relay = { station_id: number; name: string; url: string; approved: boolean; publication: Publication | null; click_count: number };
type SiteAd = { id: number; title: string; description: string; sponsor_name: string; link_url: string; image_url: string; placement: string; is_enabled: boolean; sort_order: number };
const blankArticle: ArticleDraft = { slug: "", title: "", summary: "", category: "", author: "", markdown: "", seo_title: "", seo_description: "", status: "draft" };
const blankPublication: Publication = { tagline: "", description: "", link_url: "", sort_order: 100, is_enabled: true, is_sponsored: false };
const blankAd = { title: "", description: "", sponsor_name: "", link_url: "", image_url: "", placement: "home_hero", is_enabled: true, sort_order: 100 };
const articleFields = [["title", "标题"], ["slug", "网址标识（英文、数字和短横线）"], ["category", "栏目"], ["author", "作者"], ["summary", "摘要"], ["seo_title", "搜索标题"], ["seo_description", "搜索摘要"]] as const;
const settingFields = [["notice_title", "公告标题"], ["notice_content", "公告内容"], ["notice_link", "公告链接"], ["google_verification", "Google 验证码"], ["bing_verification", "Bing 验证码"], ["baidu_verification", "百度验证码"], ["ga_measurement_id", "GA4 测量 ID"], ["baidu_analytics_id", "百度统计 ID"]] as const;

export function SitePublishingPanel(props: Props) {
  const [site, setSite] = useState<SiteId>("pricememo");
  return <section><div className="site-publishing-toolbar"><label htmlFor="publishing-site">当前站点</label><select id="publishing-site" value={site} onChange={e => setSite(e.target.value as SiteId)}>{Object.entries(BRANDS).map(([id, brand]) => <option key={id} value={id}>{brand.name} · {new URL(brand.url).hostname}</option>)}</select><a className="text-action" href={BRANDS[site].url} target="_blank" rel="noreferrer">打开站点 ↗</a></div><SiteEditor key={site} {...props} site={site} /></section>;
}

function SiteEditor({ apiBase, headers, site }: Props & { site: SiteId }) {
  const [tab, setTab] = useState<"articles" | "relays" | "ads" | "settings">("articles");
  const [settings, setSettings] = useState<SiteSettings | null>(null);
  const [articles, setArticles] = useState<ArticlePage | null>(null);
  const [relays, setRelays] = useState<Relay[]>([]);
  const [ads, setAds] = useState<SiteAd[]>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [articleDraft, setArticleDraft] = useState<ArticleDraft | null>(null);
  const [articleId, setArticleId] = useState<number | null>(null);
  const [preview, setPreview] = useState(false);
  const [relayDraft, setRelayDraft] = useState<(Publication & { station_id: number; name: string }) | null>(null);
  const [adDraft, setAdDraft] = useState<(typeof blankAd & { id?: number }) | null>(null);
  const prefix = `${apiBase}/api/v1/admin/sites/${site}`;
  async function request<T>(path: string, method = "GET", body?: unknown, signal?: AbortSignal): Promise<T> {
    const res = await fetch(`${prefix}${path}`, { method, headers: { ...headers, "Content-Type": "application/json" }, ...(body === undefined ? {} : { body: JSON.stringify(body) }), signal, cache: "no-store" });
    const data = await res.json();
    if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : `请求失败（${res.status}），请检查字段内容。`);
    return data;
  }
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([request<SiteSettings>("/settings", "GET", undefined, controller.signal), request<ArticlePage>("/articles", "GET", undefined, controller.signal), request<Relay[]>("/relays", "GET", undefined, controller.signal), request<SiteAd[]>("/ads", "GET", undefined, controller.signal)])
      .then(([nextSettings, nextArticles, nextRelays, nextAds]) => { setSettings(nextSettings); setArticles(nextArticles); setRelays(nextRelays); setAds(nextAds); })
      .catch(e => { if (!controller.signal.aborted) setError(e.message); });
    return () => controller.abort();
    // Remounted whenever the selected site or verified admin key changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  async function action(run: () => Promise<void>) {
    if (busy) return;
    setBusy(true); setError(""); setMessage("");
    try { await run(); } catch (e) { setError(e instanceof Error ? e.message : "操作失败"); } finally { setBusy(false); }
  }
  async function saveArticle(status: "draft" | "published") {
    if (!articleDraft) return;
    await action(async () => {
      const saved = await request<Article>(articleId ? `/articles/${articleId}` : "/articles", articleId ? "PUT" : "POST", { ...articleDraft, status });
      setArticleId(saved.id); setArticleDraft({ ...articleDraft, status });
      setArticles(await request<ArticlePage>("/articles"));
      setMessage(status === "published" ? "文章已发布到当前站点" : "已保存草稿，公开页面不可见");
    });
  }
  return <div className="space-y-6">
    <nav className="site-publishing-toolbar" aria-label="站点管理">{([ ["articles", "文章"], ["relays", "中转站"], ["ads", "广告"], ["settings", "公告与 SEO"] ] as const).map(([id, label]) => <button key={id} type="button" className={tab === id ? "button-primary" : "button-secondary"} onClick={() => setTab(id)} aria-pressed={tab === id}>{label}</button>)}</nav>
    {error && <p role="alert" className="text-[color:var(--danger)]">{error}</p>}{message && <p role="status">{message}</p>}
    {!settings || !articles ? <p role="status">{error ? "未加载站点内容，请重新选择站点重试。" : "正在加载站点内容…"}</p> : <fieldset disabled={busy} className="min-w-0">
      {tab === "articles" && <div className="space-y-6">
        {!articleDraft ? <><button className="button-primary" type="button" onClick={() => { setArticleId(null); setArticleDraft({ ...blankArticle }); setPreview(false); }}>新建文章</button><div className="site-publishing-list">{articles.items.length ? articles.items.map(article => <div className="site-publishing-item" key={article.id}><div><strong>{article.title}</strong><p className="article-meta">{article.status === "published" ? "已发布" : "草稿"} · {article.category || "未分类"} · /articles/{article.slug}</p></div><button className="button-secondary" type="button" onClick={() => action(async () => { const value = await request<Article>(`/articles/${article.id}`); setArticleId(value.id); setArticleDraft(Object.fromEntries(Object.keys(blankArticle).map(key => [key, value[key as keyof Article] || ""])) as ArticleDraft); setPreview(false); })}>编辑</button></div>) : <p>本站还没有文章。</p>}</div><div className="site-editor-actions">{articles.page > 1 && <button type="button" className="button-secondary" onClick={() => action(async () => setArticles(await request<ArticlePage>(`/articles?page=${articles.page - 1}`)))}>上一页</button>}{articles.page * articles.page_size < articles.total && <button type="button" className="button-secondary" onClick={() => action(async () => setArticles(await request<ArticlePage>(`/articles?page=${articles.page + 1}`)))}>下一页</button>}</div></> : <div className="site-editor">
          <div className="site-editor-actions"><button type="button" className="button-secondary" onClick={() => setArticleDraft(null)}>返回列表</button><button type="button" className="button-secondary" onClick={() => setPreview(!preview)}>{preview ? "继续编辑" : "预览"}</button>{articleDraft.status === "published" && <a href={`${BRANDS[site].url}/articles/${articleDraft.slug}`} target="_blank" rel="noreferrer" className="text-action">查看文章 ↗</a>}</div>
          {preview ? <article className="article-body"><h1 className="text-3xl mb-6">{articleDraft.title}</h1><MarkdownView content={articleDraft.markdown} /></article> : <><div className="site-editor-row">{articleFields.map(([key, label]) => <label key={key}>{label}<input value={articleDraft[key]} onChange={e => setArticleDraft({ ...articleDraft, [key]: e.target.value })} /></label>)}</div><label>正文（Markdown）<textarea className="markdown-input" value={articleDraft.markdown} onChange={e => setArticleDraft({ ...articleDraft, markdown: e.target.value })} /></label></>}
          <div className="site-editor-actions"><button className="button-secondary" type="button" onClick={() => saveArticle("draft")}>{articleDraft.status === "published" ? "撤下并保存草稿" : "保存草稿"}</button><button className="button-primary" type="button" onClick={() => saveArticle("published")}>{articleDraft.status === "published" ? "更新已发布文章" : `发布到 ${BRANDS[site].name}`}</button></div>
        </div>}
      </div>}
      {tab === "relays" && (site === "pricememo" ? <p>PriceMemo 中转站继续在“广告与中转站”管理。</p> : <div className="space-y-5">
        <p className="text-sm text-[color:var(--muted)]">选择本站收录的中转站。新增服务商和监测配置在“广告与中转站”管理。</p>
        {relayDraft ? <div className="site-editor"><h3>{relayDraft.name}</h3>{([ ["tagline", "本站简介"], ["description", "本站介绍"], ["link_url", "本站推广链接（留空使用原链接）"] ] as const).map(([key, label]) => <label key={key}>{label}<textarea value={relayDraft[key]} onChange={e => setRelayDraft({ ...relayDraft, [key]: e.target.value })} /></label>)}<label>排序<input type="number" min="0" value={relayDraft.sort_order} onChange={e => setRelayDraft({ ...relayDraft, sort_order: Number(e.target.value) })} /></label><label>展示<select value={String(relayDraft.is_enabled)} onChange={e => setRelayDraft({ ...relayDraft, is_enabled: e.target.value === "true" })}><option value="true">上架</option><option value="false">下架</option></select></label><label>赞助标识<select value={String(relayDraft.is_sponsored)} onChange={e => setRelayDraft({ ...relayDraft, is_sponsored: e.target.value === "true" })}><option value="false">普通收录</option><option value="true">赞助</option></select></label><div className="site-editor-actions"><button className="button-primary" onClick={() => action(async () => { const { station_id, name, ...payload } = relayDraft; await request(`/relays/${station_id}`, "PUT", payload); setRelays(await request<Relay[]>("/relays")); setRelayDraft(null); setMessage("本站中转站配置已保存"); })}>保存</button><button className="button-secondary" onClick={() => setRelayDraft(null)}>取消</button></div></div> : <div className="site-publishing-list">{relays.map(relay => <div key={relay.station_id} className="site-publishing-item"><div><strong>{relay.name}</strong><p className="article-meta">{relay.publication?.is_enabled ? "本站已收录" : "本站未展示"}{!relay.approved ? " · 来源未批准或已停用" : ""} · 本站点击 {relay.click_count}</p></div><button className="button-secondary" onClick={() => setRelayDraft({ ...blankPublication, ...relay.publication, station_id: relay.station_id, name: relay.name })}>配置</button></div>)}</div>}
      </div>)}
      {tab === "ads" && (site === "pricememo" ? <p>PriceMemo 广告继续在“广告与中转站”管理。</p> : <div className="space-y-5">{adDraft ? <div className="site-editor">{([ ["title", "标题"], ["sponsor_name", "赞助商"], ["description", "描述"], ["link_url", "链接"], ["image_url", "图片地址"] ] as const).map(([key, label]) => <label key={key}>{label}<input value={adDraft[key]} onChange={e => setAdDraft({ ...adDraft, [key]: e.target.value })} /></label>)}<div className="site-editor-row"><label>广告位<select value={adDraft.placement} onChange={e => setAdDraft({ ...adDraft, placement: e.target.value })}>{Object.entries({ home_hero: "首页", catalog_top: "报价目录", product_offers: "商品报价", relay_hub: "中转站", sidebar: "侧栏" }).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><label>排序<input type="number" min="0" value={adDraft.sort_order} onChange={e => setAdDraft({ ...adDraft, sort_order: Number(e.target.value) })} /></label><label>状态<select value={String(adDraft.is_enabled)} onChange={e => setAdDraft({ ...adDraft, is_enabled: e.target.value === "true" })}><option value="true">启用</option><option value="false">停用</option></select></label></div><div className="site-editor-actions"><button className="button-primary" onClick={() => action(async () => { const { id, ...payload } = adDraft; await request(id ? `/ads/${id}` : "/ads", id ? "PATCH" : "POST", payload); setAds(await request<SiteAd[]>("/ads")); setAdDraft(null); setMessage("广告已保存"); })}>保存广告</button><button className="button-secondary" onClick={() => setAdDraft(null)}>取消</button></div></div> : <><button className="button-primary" onClick={() => setAdDraft({ ...blankAd })}>新增广告</button><div className="site-publishing-list">{ads.map(ad => <div className="site-publishing-item" key={ad.id}><div><strong>{ad.title}</strong><p className="article-meta">{ad.placement} · {ad.is_enabled ? "启用" : "停用"}</p></div><button className="button-secondary" onClick={() => setAdDraft(Object.fromEntries([...Object.keys(blankAd), "id"].map(key => [key, ad[key as keyof SiteAd]])) as (typeof blankAd & { id?: number }))}>编辑</button></div>)}</div></>}</div>)}
      {tab === "settings" && <form className="site-editor" onSubmit={e => { e.preventDefault(); action(async () => { const { configured, ...payload } = settings; setSettings(await request<SiteSettings>("/settings", "PUT", payload)); setMessage("本站配置已保存"); }); }}>
        {site === "pricememo" && <p className="text-sm">PriceMemo 公告和运营开关继续使用“运营与配置”；此处保存搜索引擎验证和统计配置。</p>}
        <div className="site-editor-row">{settingFields.filter(([key]) => site !== "pricememo" || !key.startsWith("notice_")).map(([key, label]) => <label key={key}>{label}<input value={settings[key]} onChange={e => setSettings({ ...settings, [key]: e.target.value })} /></label>)}{site !== "pricememo" && ([ ["advertise_enabled", "商务合作入口"], ["ad_slots_enabled", "广告展示"], ["relay_hub_enabled", "中转站目录"] ] as const).map(([key, label]) => <label key={key}>{label}<select value={String(settings[key])} onChange={e => setSettings({ ...settings, [key]: e.target.value === "true" })}><option value="true">开启</option><option value="false">关闭</option></select></label>)}</div><button type="submit" className="button-primary justify-self-start">保存配置</button>
      </form>}
    </fieldset>}
  </div>;
}
