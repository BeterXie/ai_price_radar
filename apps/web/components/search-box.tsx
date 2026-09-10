"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, MagnifyingGlass } from "@phosphor-icons/react";

export function SearchBox({ defaultValue = "" }: { defaultValue?: string }) {
  const [value, setValue] = useState(defaultValue);
  const router = useRouter();
  function submit(event: FormEvent) {
    event.preventDefault();
    const query = value.trim();
    router.push(query ? `/products?q=${encodeURIComponent(query)}` : "/products");
  }
  return (
    <form onSubmit={submit} role="search" className="search-shell flex w-full items-center focus-within:border-[color:var(--focus)]">
      <MagnifyingGlass size={21} className="shrink-0 text-[#7c8c79]" aria-hidden="true" />
      <input
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder="搜索产品、品牌或交付方式…"
        aria-label="搜索产品或交付方式"
        className="min-w-0 flex-1 bg-transparent outline-none placeholder:text-[color:var(--muted)]/70"
      />
      <button className="button-primary tactile shrink-0">
        查报价 <ArrowRight size={16} weight="bold" />
      </button>
    </form>
  );
}
