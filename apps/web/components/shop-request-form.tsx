"use client";

import { FormEvent, useState } from "react";
import { CheckCircle, Storefront } from "@phosphor-icons/react";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
const LDXP_HOSTS = new Set(["pay.ldxp.cn", "www.ldxp.cn", "ldxp.cn"]);
type SourceType = "ldxp" | "merchant_feed";
type SubmitState = "idle" | "sending" | "submitted" | "pending" | "known" | "limited" | "invalid" | "error";
type ShopRequestResponse = { source_type: SourceType; status: "submitted" | "already_pending" | "already_known"; request_id: number | null; shop_token: string };

function isValidSourceUrl(value: string, sourceType: SourceType) {
  try {
    const url = new URL(value);
    if (sourceType === "merchant_feed") return url.protocol === "https:" && !url.username && !url.password && Boolean(url.hostname);
    return LDXP_HOSTS.has(url.hostname.toLowerCase()) && /^\/shop\/[A-Za-z0-9._~-]+\/?$/.test(url.pathname);
  } catch { return false; }
}

export function ShopRequestForm() {
  const [sourceType, setSourceType] = useState<SourceType>("ldxp");
  const [shopUrl, setShopUrl] = useState("");
  const [shopName, setShopName] = useState("");
  const [contact, setContact] = useState("");
  const [note, setNote] = useState("");
  const [state, setState] = useState<SubmitState>("idle");

  function resetSource(type: SourceType) { setSourceType(type); setShopUrl(""); setState("idle"); }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!isValidSourceUrl(shopUrl.trim(), sourceType)) { setState("invalid"); return; }
    setState("sending");
    try {
      const response = await fetch(`${API}/api/v1/shop-requests`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ source_type: sourceType, shop_url: shopUrl.trim(), shop_name: shopName.trim(), contact: contact.trim(), note: note.trim() }) });
      if (response.status === 429) { setState("limited"); return; }
      if (!response.ok) { setState(response.status === 422 ? "invalid" : "error"); return; }
      const result = await response.json() as ShopRequestResponse;
      setState(result.status === "already_known" ? "known" : result.status === "already_pending" ? "pending" : "submitted");
    } catch { setState("error"); }
  }

  const complete = ["submitted", "pending", "known"].includes(state);
  const feedback: Record<Exclude<SubmitState, "idle" | "sending">, string> = {
    submitted: "申请已提交。审核与首次读取通过后，符合范围的商品会进入报价目录。",
    pending: "这个来源已经在审核队列中，无需重复提交。",
    known: "这个来源已经进入系统，无需重复申请。",
    limited: "提交过于频繁，请稍后再试。",
    invalid: sourceType === "ldxp" ? "请输入有效的链动小铺公开店铺链接，例如 https://pay.ldxp.cn/shop/ABC123。" : "请输入可公开访问的 HTTPS JSON Feed 地址。不能使用本地、私网或带账号密码的 URL。",
    error: "提交失败，请稍后再试。",
  };
  const placeholder = sourceType === "ldxp" ? "https://pay.ldxp.cn/shop/ABC123" : "https://merchant.example.com/ai-price-feed.json";

  return <form onSubmit={submit} className="rounded-[18px] border hairline bg-[color:var(--panel)] p-5 sm:p-7">
    <div className="flex items-center gap-3 border-b hairline pb-5"><span className="grid h-10 w-10 place-items-center rounded-[10px] bg-[color:var(--accent)] text-[color:var(--accent-ink)]">{complete ? <CheckCircle size={22} weight="fill" /> : <Storefront size={22} />}</span><div><h2 className="font-semibold">提交公开来源</h2><p className="mt-1 text-sm text-[color:var(--muted)]">联系方式仅用于核对，不会公开展示。</p></div></div>
    <fieldset className="mt-6"><legend className="text-sm font-medium">来源类型</legend><div className="mt-2 grid grid-cols-2 gap-2"><button type="button" onClick={() => resetSource("ldxp")} className={`rounded-[10px] border px-3 py-3 text-sm ${sourceType === "ldxp" ? "border-black bg-black text-white" : "hairline bg-white"}`}>链动小铺</button><button type="button" onClick={() => resetSource("merchant_feed")} className={`rounded-[10px] border px-3 py-3 text-sm ${sourceType === "merchant_feed" ? "border-black bg-black text-white" : "hairline bg-white"}`}>商家 JSON Feed</button></div></fieldset>
    <div className="mt-5 grid gap-5">
      <label className="grid gap-2 text-sm font-medium" htmlFor="shop-url">{sourceType === "ldxp" ? "店铺链接" : "Feed 地址"}<input id="shop-url" name="shop_url" type="url" required value={shopUrl} onChange={(event) => { setShopUrl(event.target.value); if (state !== "sending") setState("idle"); }} placeholder={placeholder} className="rounded-[10px] border hairline bg-white px-3 py-3 text-sm outline-none focus:border-black"/><span className="text-xs font-normal leading-5 text-black/50">{sourceType === "ldxp" ? "支持 pay.ldxp.cn、www.ldxp.cn 和 ldxp.cn 的公开店铺链接。" : "Feed 必须使用公开 HTTPS，返回商品数组或包含 shop、updated_at、items 的 JSON 对象。"}</span></label>
      <label className="grid gap-2 text-sm font-medium" htmlFor="shop-name">来源名称 <span className="font-normal text-black/45">选填</span><input id="shop-name" maxLength={120} value={shopName} onChange={(e)=>setShopName(e.target.value)} className="rounded-[10px] border hairline bg-white px-3 py-3 text-sm outline-none focus:border-black"/></label>
      <label className="grid gap-2 text-sm font-medium" htmlFor="shop-contact">联系邮箱 <span className="font-normal text-black/45">必填</span><input id="shop-contact" name="contact" type="email" required maxLength={200} value={contact} onChange={(e)=>setContact(e.target.value)} placeholder="you@example.com" className="rounded-[10px] border hairline bg-white px-3 py-3 text-sm outline-none focus:border-black"/><span className="text-xs font-normal leading-5 text-black/50">仅用于申请状态通知，不会公开展示。</span></label>
      <label className="grid gap-2 text-sm font-medium" htmlFor="shop-note">申请说明 <span className="font-normal text-black/45">选填</span><textarea id="shop-note" maxLength={1000} rows={4} value={note} onChange={(e)=>setNote(e.target.value)} placeholder={sourceType === "merchant_feed" ? "可说明 Feed 更新频率、字段含义和主营产品。" : "可填写主营的 AI 产品或需要补充核对的信息。"} className="resize-y rounded-[10px] border hairline bg-white px-3 py-3 text-sm outline-none focus:border-black"/></label>
      <label className="flex items-start gap-3 text-sm leading-6 text-black/65"><input type="checkbox" required className="mt-1 h-4 w-4 accent-black"/><span>我确认该来源可公开访问，并有权提交此收录申请。</span></label>
    </div>
    <button type="submit" disabled={state === "sending" || complete} className="tactile mt-6 w-full rounded-[10px] bg-[color:var(--ink)] px-5 py-3 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-55">{state === "sending" ? "提交中" : complete ? "已记录" : "提交申请"}</button>
    {state !== "idle" && state !== "sending" && <p role={["invalid","error","limited"].includes(state) ? "alert" : "status"} className={`mt-4 rounded-[10px] px-4 py-3 text-sm leading-6 ${complete ? "bg-[color:var(--accent)] text-[color:var(--accent-ink)]" : "bg-[#f2d8d2] text-[color:var(--danger)]"}`}>{feedback[state]}</p>}
  </form>;
}
