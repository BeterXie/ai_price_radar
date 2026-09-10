"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, MagnifyingGlass, X } from "@phosphor-icons/react";

export function SearchBox({ defaultValue = "", compact = false }: { defaultValue?: string; compact?: boolean }) {
  const [value, setValue] = useState(defaultValue);
  const router = useRouter();

  function submit(event: FormEvent) {
    event.preventDefault();
    const query = value.trim();
    router.push(query ? `/products?q=${encodeURIComponent(query)}` : "/products");
  }

  return (
    <form onSubmit={submit} role="search" className={`search-form ${compact ? "compact" : ""}`}>
      <MagnifyingGlass size={19} aria-hidden="true" />
      <input value={value} onChange={(event) => setValue(event.target.value)} placeholder="搜索产品、品牌或交付方式…" aria-label="搜索产品、品牌或交付方式" />
      {value ? <button type="button" className="clear-search" onClick={() => setValue("")} aria-label="清空搜索"><X size={14} /></button> : null}
      <button className="button primary" type="submit">查报价 <ArrowRight size={15} /></button>
    </form>
  );
}
