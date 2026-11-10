"use client";

import Link from "next/link";
import { CaretDown, Storefront } from "@phosphor-icons/react";
import type { Offer } from "@/lib/types";
import { SITE_ID } from "@/lib/brands";
import { DELIVERY_TYPE_LABELS, PERIOD_LABELS } from "@/lib/catalog";
import { stockLabel } from "@/lib/format";

export function BrandOfferSummary({ offer, price, stock, shops, productName, href }: { offer: Offer; price: string; stock: number; shops: number; productName?: string; href?: string }) {
  const identity = <div className="brand-offer-identity">{productName && href && <Link href={href}>{productName}</Link>}<h3>{offer.original_name}</h3><p><Storefront size={14} />{shops} 家店铺<span>{DELIVERY_TYPE_LABELS[offer.delivery_type] || offer.delivery_type} · {PERIOD_LABELS[offer.service_period] || offer.service_period}</span></p>{!offer.is_comparable ? <small className="offer-caution">相关商品，不直接比价</small> : !offer.is_trusted_price ? <small className="offer-caution">价格偏离同类报价</small> : null}</div>;
  const availability = <span className={`brand-offer-stock ${stock > 0 ? "available" : ""}`}>{stock > 0 ? "有货" : stockLabel(offer.stock_status)}</span>;
  if (SITE_ID === "pricein") return <summary className="brand-offer-summary shop-offer-summary"><div className="shop-offer-top">{availability}<span>#{offer.id}</span></div>{identity}<div className="shop-offer-bottom"><strong>{price}</strong><span>比较店铺 <CaretDown size={16} /></span></div></summary>;
  if (SITE_ID === "aisi") return <summary className="brand-offer-summary editorial-offer-summary"><div className="editorial-offer-marker" aria-hidden>↗</div>{identity}<div className="editorial-offer-price"><strong>{price}</strong>{availability}<span>展开来源 <CaretDown size={16} /></span></div></summary>;
  return <summary className={`brand-offer-summary ${SITE_ID === "aiprice" ? "terminal-offer-summary" : "index-offer-summary"}`}><span className="offer-record-number">#{offer.id}</span>{identity}{availability}<strong className="brand-offer-price">{price}</strong><CaretDown size={16} /></summary>;
}
