"use client";

import { FormEvent, useState } from "react";
import { CheckCircle, Storefront } from "@phosphor-icons/react";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
const LDXP_HOSTS = new Set(["pay.ldxp.cn", "www.ldxp.cn", "ldxp.cn"]);

type SubmitState = "idle" | "sending" | "submitted" | "pending" | "known" | "limited" | "invalid" | "error";

type ShopRequestResponse = {
  status: "submitted" | "already_pending" | "already_known";
  request_id: number | null;
  shop_token: string;
};

function isValidShopUrl(value: string) {
  try {
    const url = new URL(value);
    return LDXP_HOSTS.has(url.hostname.toLowerCase()) && /^\/shop\/[A-Za-z0-9._~-]+\/?$/.test(url.pathname);
  } catch {
    return false;
  }
}

export function ShopRequestForm() {
  const [shopUrl, setShopUrl] = useState("");
  const [shopName, setShopName] = useState("");
  const [contact, setContact] = useState("");
  const [note, setNote] = useState("");
  const [state, setState] = useState<SubmitState>("idle");

  function updateShopUrl(value: string) {
    setShopUrl(value);
    if (state !== "sending") setState("idle");
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!isValidShopUrl(shopUrl.trim())) {
      setState("invalid");
      return;
    }

    setState("sending");
    try {
      const response = await fetch(`${API}/api/v1/shop-requests`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          shop_url: shopUrl.trim(),
          shop_name: shopName.trim(),
          contact: contact.trim(),
          note: note.trim(),
        }),
      });
      if (response.status === 429) {
        setState("limited");
        return;
      }
      if (!response.ok) {
        setState(response.status === 422 ? "invalid" : "error");
        return;
      }
      const result = (await response.json()) as ShopRequestResponse;
      setState(
        result.status === "already_known"
          ? "known"
          : result.status === "already_pending"
            ? "pending"
            : "submitted",
      );
    } catch {
      setState("error");
    }
  }

  const complete = state === "submitted" || state === "pending" || state === "known";
  const feedback = {
    submitted: "申请已提交。审核和首次抓取完成后，符合收录范围的商品会出现在报价目录中。",
    pending: "这家店已经在审核队列中，无需重复提交。",
    known: "这家店已经进入系统，无需重复申请。",
    limited: "提交过于频繁，请稍后再试。",
    invalid: "请输入有效的链动小铺公开店铺链接，例如 https://pay.ldxp.cn/shop/ABC123。",
    error: "提交失败，请稍后再试。",
  } as const;

  return (
    <form onSubmit={submit} className="rounded-[18px] border hairline bg-[color:var(--panel)] p-5 sm:p-7">
      <div className="flex items-center gap-3 border-b hairline pb-5">
        <span className="grid h-10 w-10 place-items-center rounded-[10px] bg-[color:var(--accent)] text-[color:var(--accent-ink)]">
          {complete ? <CheckCircle size={22} weight="fill" /> : <Storefront size={22} />}
        </span>
        <div>
          <h2 className="font-semibold">提交店铺资料</h2>
          <p className="mt-1 text-sm text-[color:var(--muted)]">联系方式仅用于核对申请，不会公开展示。</p>
        </div>
      </div>

      <div className="mt-6 grid gap-5">
        <label className="grid gap-2 text-sm font-medium" htmlFor="shop-url">
          店铺链接
          <input
            id="shop-url"
            name="shop_url"
            type="url"
            required
            autoComplete="url"
            value={shopUrl}
            onChange={(event) => updateShopUrl(event.target.value)}
            placeholder="https://pay.ldxp.cn/shop/ABC123"
            aria-describedby="shop-url-help"
            className="rounded-[10px] border hairline bg-white px-3 py-3 text-sm outline-none focus:border-black"
          />
          <span id="shop-url-help" className="text-xs font-normal text-black/50">当前支持 pay.ldxp.cn、www.ldxp.cn 和 ldxp.cn 的公开店铺链接。</span>
        </label>

        <label className="grid gap-2 text-sm font-medium" htmlFor="shop-name">
          店铺名称 <span className="font-normal text-black/45">选填</span>
          <input
            id="shop-name"
            name="shop_name"
            maxLength={120}
            value={shopName}
            onChange={(event) => setShopName(event.target.value)}
            className="rounded-[10px] border hairline bg-white px-3 py-3 text-sm outline-none focus:border-black"
          />
        </label>

        <label className="grid gap-2 text-sm font-medium" htmlFor="shop-contact">
          联系方式 <span className="font-normal text-black/45">选填</span>
          <input
            id="shop-contact"
            name="contact"
            maxLength={200}
            autoComplete="email"
            value={contact}
            onChange={(event) => setContact(event.target.value)}
            placeholder="邮箱、微信或其他可联系账号"
            className="rounded-[10px] border hairline bg-white px-3 py-3 text-sm outline-none focus:border-black"
          />
        </label>

        <label className="grid gap-2 text-sm font-medium" htmlFor="shop-note">
          申请说明 <span className="font-normal text-black/45">选填</span>
          <textarea
            id="shop-note"
            name="note"
            maxLength={1000}
            rows={4}
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder="可填写主营的 AI 产品或需要补充核对的信息。"
            className="resize-y rounded-[10px] border hairline bg-white px-3 py-3 text-sm outline-none focus:border-black"
          />
        </label>

        <label className="flex items-start gap-3 text-sm leading-6 text-black/65">
          <input type="checkbox" required className="mt-1 h-4 w-4 accent-black" />
          <span>我确认店铺页面可公开访问，并有权提交此收录申请。</span>
        </label>
      </div>

      <button
        type="submit"
        disabled={state === "sending" || complete}
        className="tactile mt-6 w-full rounded-[10px] bg-[color:var(--ink)] px-5 py-3 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-55"
      >
        {state === "sending" ? "提交中" : complete ? "已记录" : "提交申请"}
      </button>

      {state !== "idle" && state !== "sending" && (
        <p
          role={state === "invalid" || state === "error" || state === "limited" ? "alert" : "status"}
          aria-live="polite"
          className={`mt-4 rounded-[10px] px-4 py-3 text-sm leading-6 ${
            complete
              ? "bg-[color:var(--accent)] text-[color:var(--accent-ink)]"
              : "bg-[#f2d8d2] text-[color:var(--danger)]"
          }`}
        >
          {feedback[state]}
        </p>
      )}
    </form>
  );
}
