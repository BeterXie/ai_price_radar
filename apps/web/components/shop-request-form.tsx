"use client";

import Link from "next/link";
import { FormEvent, useRef, useState } from "react";
import { CheckCircle, Storefront } from "@phosphor-icons/react";
import { isValidPublicSourceUrl, SOURCE_INTAKE_COPY, SOURCE_INTAKE_OPTIONS, type IntakeSourceType } from "@/lib/source-intake.mjs";
import { RelayProbeFields, type RelayProbeDraft } from "@/components/relay-probe-fields";
import { RelayGroupFields, groupInputs, type RelayGroupDraft } from "@/components/relay-group-fields";
import { RelayProfileFields, EMPTY_RELAY_PROFILE, relayProfileInputs, relayProfileError } from "@/components/relay-profile-fields";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "";
type SubmitState = "idle" | "sending" | "submitted" | "pending" | "known" | "limited" | "invalid" | "email_invalid" | "unauthenticated" | "forbidden" | "error";
type ShopRequestResponse = { source_type: string; declared_platform: string; detected_platform: string; detection_message: string; workflow_status: string; status: "submitted" | "already_pending" | "already_known"; request_id: number | null; shop_token: string };

export function ShopRequestForm({ initialSourceType = "ldxp" }: { initialSourceType?: IntakeSourceType }) {
  const [sourceType, setSourceType] = useState<IntakeSourceType>(initialSourceType);
  const [relay, setRelay] = useState<RelayProbeDraft>({ base_url: "", api_key: "", probe_protocol: "openai", probe_model: "", monitor_enabled: true });
  const [groups, setGroups] = useState<RelayGroupDraft[]>([]);
  const [profile, setProfile] = useState({ ...EMPTY_RELAY_PROFILE });
  const [shopUrl, setShopUrl] = useState("");
  const [shopName, setShopName] = useState("");
  const [contact, setContact] = useState("");
  const [note, setNote] = useState("");
  const [state, setState] = useState<SubmitState>("idle");
  const [detectionMessage, setDetectionMessage] = useState("");
  const [validationMessage, setValidationMessage] = useState("");
  const [authorizationConfirmed, setAuthorizationConfirmed] = useState(false);
  const requestSequence = useRef(0);

  function resetSource(type: IntakeSourceType) {
    if (state === "sending") return;
    requestSequence.current += 1;
    setSourceType(type);
    setShopUrl("");
    setGroups([]);
    setProfile({ ...EMPTY_RELAY_PROFILE });
    setValidationMessage("");
    setState("idle");
    setDetectionMessage("");
    setRelay({ base_url: "", api_key: "", probe_protocol: "openai", probe_model: "", monitor_enabled: true });
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setValidationMessage("");
    if (!isValidPublicSourceUrl(shopUrl.trim())) { setState("invalid"); return; }
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(contact.trim())) { setState("email_invalid"); return; }
    if (!authorizationConfirmed) { setState("forbidden"); return; }
    if (sourceType === "relay") {
      const error = relayProfileError(profile);
      if (error) { setValidationMessage(error); setState("invalid"); return; }
    }
    const sequence = ++requestSequence.current;
    setState("sending");
    try {
      const response = await fetch(`${API}/api/v1/${sourceType === "relay" ? "relay-requests" : "shop-requests"}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(sourceType === "relay" ? {
          ...relay, ...relayProfileInputs(profile), groups: groupInputs(groups), name: shopName.trim(), url: shopUrl.trim(),
          contact: contact.trim(), note: note.trim(), authorization_confirmed: true,
        } : {
          source_type: sourceType,
          shop_url: shopUrl.trim(),
          shop_name: shopName.trim(),
          contact: contact.trim(),
          note: note.trim(),
          authorization_confirmed: true,
          consent_version: "shop-source-submission-v1",
        }),
      });
      if (sequence !== requestSequence.current) return;
      if (response.status === 429) { setState("limited"); return; }
      if (response.status === 401) { setState("unauthenticated"); return; }
      if (response.status === 403) { setState("forbidden"); return; }
      if (!response.ok) {
        if (response.status === 422) {
          const detail = await response.json().catch(() => null) as { detail?: unknown } | null;
          const emailError = Array.isArray(detail?.detail) && detail.detail.some((item) => item.loc?.includes("contact"));
          if (!emailError && sourceType === "relay") {
            const labels: Record<string, string> = { tagline: "一句话简介", description: "详细说明", supported_models: "支持的模型", tags: "特性标签", price_note: "价格说明", billing_note: "计费方式" };
            const field = Array.isArray(detail?.detail) ? detail.detail.find((item) => item.loc?.some((part: string) => labels[part])) : null;
            const label = field?.loc?.map((part: string) => labels[part]).find(Boolean);
            if (label) setValidationMessage(`请检查${label}是否填写完整，且未超过标注的数量或长度限制。`);
          }
          setState(emailError ? "email_invalid" : "invalid");
        } else {
          setState("error");
        }
        return;
      }
      const result = await response.json() as ShopRequestResponse;
      setRelay((value) => ({ ...value, api_key: "" }));
      if (sequence !== requestSequence.current) return;
      setDetectionMessage(result.detection_message);
      setState(result.status === "already_known" ? "known" : result.status === "already_pending" ? "pending" : "submitted");
    } catch {
      if (sequence === requestSequence.current) setState("error");
    }
  }

  const complete = state === "submitted" || state === "pending" || state === "known";
  const feedback: Record<Exclude<SubmitState, "idle" | "sending">, string> = {
    submitted: sourceType === "relay" ? "中转站申请已收到，审核通过后在中转站专区展示并开始接口检测。" : `${detectionMessage ? `${detectionMessage} ` : ""}申请已收到。审核通过并成功读取商品后，符合收录范围的报价会显示在目录中。`,
    pending: `${detectionMessage ? `${detectionMessage} ` : ""}这个来源已经在审核队列中，无需重复提交。`,
    known: `${detectionMessage ? `${detectionMessage} ` : ""}系统中已有这条来源记录，无需重复提交。`,
    limited: "提交过于频繁，请稍后再试。",
    invalid: validationMessage || (sourceType === "relay" ? "请核对站点名称、公开展示资料、公开 HTTPS 地址、Base URL、检测密钥及模型 ID。" : "请输入可公开访问的 HTTPS 地址。不能使用本地、内部或带账号密码的 URL。"),
    email_invalid: "请输入完整有效的联系邮箱，例如 you@example.com。",
    unauthenticated: "请先登录，并使用已验证的登录邮箱提交申请。",
    forbidden: "联系邮箱必须与已验证的登录邮箱一致，并确认你有权提交该来源。",
    error: "提交失败，请稍后再试。",
  };
  const copy = SOURCE_INTAKE_COPY[sourceType];

  function startAnother() {
    setSourceType(initialSourceType);
    setShopUrl("");
    setShopName("");
    setContact("");
    setNote("");
    setGroups([]);
    setProfile({ ...EMPTY_RELAY_PROFILE });
    setValidationMessage("");
    setDetectionMessage("");
    setAuthorizationConfirmed(false);
    setRelay({ base_url: "", api_key: "", probe_protocol: "openai", probe_model: "", monitor_enabled: true });
    requestSequence.current += 1;
    setState("idle");
  }

  if (complete) {
    const resultTitle = state === "known" ? "来源已经收录" : state === "pending" ? "来源正在审核" : "申请已记录";
    return (
      <section className="shop-submit-form evidence-callout" role="status" data-vds-layer="evidence">
        <span className="grid size-11 place-items-center rounded-[9px] bg-[color:var(--success-soft)] text-[color:var(--success)]"><CheckCircle size={25} weight="fill" /></span>
        <p className="section-kicker mt-5">申请状态</p>
        <h2 className="mt-2 text-2xl font-semibold">{resultTitle}</h2>
        <p className="mt-3 text-sm leading-7 text-[color:var(--muted)]">{feedback[state]}</p>
        <div className="mt-6 flex flex-wrap gap-3">
          <button type="button" onClick={startAnother} className="button-primary tactile">提交另一个来源</button>
          <Link href="/products" className="button-secondary tactile">浏览报价目录</Link>
        </div>
      </section>
    );
  }

  return <form onSubmit={submit} className="shop-submit-form surface-panel p-5 sm:p-7" data-vds-layer="evidence">
    <div className="flex items-center gap-3 border-b hairline pb-5"><span className="grid h-10 w-10 place-items-center rounded-[10px] bg-[color:var(--accent)] text-[color:var(--accent-ink)]">{complete ? <CheckCircle size={22} weight="fill" /> : <Storefront size={22} />}</span><div><h2 className="font-semibold">提交商品来源</h2><p className="mt-1 text-sm text-[color:var(--muted)]">联系方式仅用于核对，不会公开展示。</p></div></div>
    <fieldset disabled={state === "sending"} className="mt-6"><legend className="text-sm font-medium">来源类型</legend><div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2">{SOURCE_INTAKE_OPTIONS.map((option) => <button key={option.id} type="button" disabled={state === "sending"} aria-pressed={sourceType === option.id} onClick={() => resetSource(option.id)} className={`min-h-11 rounded-[8px] border px-3 py-2.5 text-sm font-medium ${sourceType === option.id ? "border-[color:var(--ink)] bg-[color:var(--ink)] text-white" : "border-[color:var(--line-strong)] bg-[color:var(--panel)]"}`}>{option.label}</button>)}</div></fieldset>
    <div className="mt-5 grid gap-5">
      <label className="grid gap-2 text-sm font-medium" htmlFor="shop-url">{copy.fieldLabel}<input id="shop-url" name="shop_url" type="url" required disabled={state === "sending"} value={shopUrl} onChange={(event) => { setShopUrl(event.target.value); if (state !== "sending") setState("idle"); }} placeholder={copy.placeholder} className="field text-sm"/><span className="text-xs font-normal leading-5 text-[color:var(--muted)]">{copy.hint}</span></label>
      <label className="grid gap-2 text-sm font-medium" htmlFor="shop-name">{sourceType === "relay" ? "中转站名称（必填）" : "来源名称（选填）"}<input id="shop-name" required={sourceType === "relay"} maxLength={sourceType === "relay" ? 100 : 120} disabled={state === "sending"} value={shopName} onChange={(e)=>setShopName(e.target.value)} className="field text-sm"/></label>
      {sourceType === "relay" && <fieldset disabled={state === "sending"}><RelayProfileFields value={profile} onChange={(patch) => { setProfile((value) => ({ ...value, ...patch })); setValidationMessage(""); if (state === "invalid") setState("idle"); }} /></fieldset>}
      {sourceType === "relay" && <fieldset disabled={state === "sending"}><RelayProbeFields value={relay} onChange={(patch) => setRelay((value) => ({ ...value, ...patch }))} required/></fieldset>}
      {sourceType === "relay" && <details><summary className="cursor-pointer text-sm">补充分组与倍率（选填）</summary><fieldset disabled={state === "sending"} className="mt-3"><RelayGroupFields groups={groups} onChange={setGroups} /></fieldset></details>}
      <label className="grid gap-2 text-sm font-medium" htmlFor="shop-contact">联系邮箱 <span className="font-normal text-[color:var(--muted)]">必填</span><input id="shop-contact" name="contact" type="email" required maxLength={200} disabled={state === "sending"} value={contact} onChange={(e)=>setContact(e.target.value)} placeholder="you@example.com" className="field text-sm"/><span className="text-xs font-normal leading-5 text-[color:var(--muted)]">必须与已验证的登录邮箱一致，仅用于申请状态通知。</span></label>
      <label className="grid gap-2 text-sm font-medium" htmlFor="shop-note">申请说明 <span className="font-normal text-[color:var(--muted)]">选填 · 仅管理员可见</span><textarea id="shop-note" maxLength={1000} rows={4} disabled={state === "sending"} value={note} onChange={(e)=>setNote(e.target.value)} placeholder={sourceType === "relay" ? "填写需要管理员核对的信息；公开介绍请填写在上方展示资料中。" : "可填写主营的 AI 产品或需要补充核对的信息。"} className="field resize-y text-sm"/></label>
      <label className="flex min-h-11 items-start gap-3 text-sm leading-6 text-[color:var(--muted)]"><input type="checkbox" required disabled={state === "sending"} checked={authorizationConfirmed} onChange={(event) => setAuthorizationConfirmed(event.target.checked)} className="mt-1 h-5 w-5 accent-[color:var(--brand-strong)]"/><span>我确认该来源可公开访问，并有权提交此收录申请。</span></label>
    </div>
    <button type="submit" disabled={state === "sending" || complete} className="button-primary tactile mt-6 w-full disabled:cursor-not-allowed disabled:opacity-55">{state === "sending" ? "提交中" : complete ? "已记录" : "提交申请"}</button>
    {state !== "idle" && state !== "sending" && <p role={["invalid","email_invalid","unauthenticated","forbidden","error","limited"].includes(state) ? "alert" : "status"} className={`mt-4 rounded-[9px] border px-4 py-3 text-sm leading-6 ${complete ? "border-[color:var(--success)]/25 bg-[color:var(--success-soft)] text-[color:var(--success)]" : "border-[color:var(--danger)]/25 bg-[color:var(--danger-soft)] text-[color:var(--danger)]"}`}>{feedback[state]}</p>}
  </form>;
}
