"use client";

import { FormEvent, useState } from "react";
import { CheckCircle, Storefront } from "@phosphor-icons/react";
import { isValidPublicSourceUrl, SOURCE_INTAKE_COPY, SOURCE_INTAKE_OPTIONS, type IntakeSourceType } from "@/lib/source-intake.mjs";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
type SubmitState = "idle" | "sending" | "submitted" | "pending" | "known" | "limited" | "invalid" | "error";
type ShopRequestResponse = { source_type: string; declared_platform: string; detected_platform: string; detection_message: string; workflow_status: string; status: "submitted" | "already_pending" | "already_known"; request_id: number | null; shop_token: string };

export function ShopRequestForm() {
  const [sourceType, setSourceType] = useState<IntakeSourceType>("auto");
  const [shopUrl, setShopUrl] = useState("");
  const [shopName, setShopName] = useState("");
  const [contact, setContact] = useState("");
  const [note, setNote] = useState("");
  const [state, setState] = useState<SubmitState>("idle");
  const [detectionMessage, setDetectionMessage] = useState("");

  function resetSource(type: IntakeSourceType) { setSourceType(type); setShopUrl(""); setState("idle"); setDetectionMessage(""); }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!isValidPublicSourceUrl(shopUrl.trim())) { setState("invalid"); return; }
    setState("sending");
    try {
      const response = await fetch(`${API}/api/v1/shop-requests`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ source_type: sourceType, shop_url: shopUrl.trim(), shop_name: shopName.trim(), contact: contact.trim(), note: note.trim() }) });
      if (response.status === 429) { setState("limited"); return; }
      if (!response.ok) { setState(response.status === 422 ? "invalid" : "error"); return; }
      const result = await response.json() as ShopRequestResponse;
      setDetectionMessage(result.detection_message);
      setState(result.status === "already_known" ? "known" : result.status === "already_pending" ? "pending" : "submitted");
    } catch { setState("error"); }
  }

  const complete = ["submitted", "pending", "known"].includes(state);
  const feedback: Record<Exclude<SubmitState, "idle" | "sending">, string> = {
    submitted: `${detectionMessage ? `${detectionMessage} ` : ""}申请已收到。审核通过并成功读取商品后，符合收录范围的报价会显示在目录中。`,
    pending: `${detectionMessage ? `${detectionMessage} ` : ""}这个来源已经在审核队列中，无需重复提交。`,
    known: `${detectionMessage ? `${detectionMessage} ` : ""}系统中已有这条来源记录，无需重复提交。`,
    limited: "提交过于频繁，请稍后再试。",
    invalid: "请输入可公开访问的 HTTPS 地址。不能使用本地、内部或带账号密码的 URL。",
    error: "提交失败，请稍后再试。",
  };
  const copy = SOURCE_INTAKE_COPY[sourceType];

  return <form onSubmit={submit} className="rounded-[18px] border hairline bg-[color:var(--panel)] p-5 sm:p-7">
    <div className="flex items-center gap-3 border-b hairline pb-5"><span className="grid h-10 w-10 place-items-center rounded-[10px] bg-[color:var(--accent)] text-[color:var(--accent-ink)]">{complete ? <CheckCircle size={22} weight="fill" /> : <Storefront size={22} />}</span><div><h2 className="font-semibold">提交商品来源</h2><p className="mt-1 text-sm text-[color:var(--muted)]">联系方式仅用于核对，不会公开展示。</p></div></div>
    <fieldset className="mt-6"><legend className="text-sm font-medium">来源类型</legend><div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2">{SOURCE_INTAKE_OPTIONS.map((option) => <button key={option.id} type="button" aria-pressed={sourceType === option.id} onClick={() => resetSource(option.id)} className={`rounded-[10px] border px-3 py-3 text-sm ${sourceType === option.id ? "border-black bg-black text-white" : "hairline bg-white"}`}>{option.label}</button>)}</div></fieldset>
    <div className="mt-5 grid gap-5">
      <label className="grid gap-2 text-sm font-medium" htmlFor="shop-url">{copy.fieldLabel}<input id="shop-url" name="shop_url" type="url" required value={shopUrl} onChange={(event) => { setShopUrl(event.target.value); if (state !== "sending") setState("idle"); }} placeholder={copy.placeholder} className="rounded-[10px] border hairline bg-white px-3 py-3 text-sm outline-none focus:border-black"/><span className="text-xs font-normal leading-5 text-black/50">{copy.hint}</span></label>
      <label className="grid gap-2 text-sm font-medium" htmlFor="shop-name">来源名称 <span className="font-normal text-black/45">选填</span><input id="shop-name" maxLength={120} value={shopName} onChange={(e)=>setShopName(e.target.value)} className="rounded-[10px] border hairline bg-white px-3 py-3 text-sm outline-none focus:border-black"/></label>
      <label className="grid gap-2 text-sm font-medium" htmlFor="shop-contact">联系邮箱 <span className="font-normal text-black/45">必填</span><input id="shop-contact" name="contact" type="email" required maxLength={200} value={contact} onChange={(e)=>setContact(e.target.value)} placeholder="you@example.com" className="rounded-[10px] border hairline bg-white px-3 py-3 text-sm outline-none focus:border-black"/><span className="text-xs font-normal leading-5 text-black/50">仅用于申请状态通知，不会公开展示。</span></label>
      <label className="grid gap-2 text-sm font-medium" htmlFor="shop-note">申请说明 <span className="font-normal text-black/45">选填</span><textarea id="shop-note" maxLength={1000} rows={4} value={note} onChange={(e)=>setNote(e.target.value)} placeholder={sourceType === "merchant_json" ? "可说明 Feed 更新频率、字段含义和主营产品。" : "可填写主营的 AI 产品或需要补充核对的信息。"} className="resize-y rounded-[10px] border hairline bg-white px-3 py-3 text-sm outline-none focus:border-black"/></label>
      <label className="flex items-start gap-3 text-sm leading-6 text-black/65"><input type="checkbox" required className="mt-1 h-4 w-4 accent-black"/><span>我确认该来源可公开访问，并有权提交此收录申请。</span></label>
    </div>
    <button type="submit" disabled={state === "sending" || complete} className="tactile mt-6 w-full rounded-[10px] bg-[color:var(--ink)] px-5 py-3 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-55">{state === "sending" ? "提交中" : complete ? "已记录" : "提交申请"}</button>
    {state !== "idle" && state !== "sending" && <p role={["invalid","error","limited"].includes(state) ? "alert" : "status"} className={`mt-4 rounded-[10px] px-4 py-3 text-sm leading-6 ${complete ? "bg-[color:var(--accent)] text-[color:var(--accent-ink)]" : "bg-[#f2d8d2] text-[color:var(--danger)]"}`}>{feedback[state]}</p>}
  </form>;
}
