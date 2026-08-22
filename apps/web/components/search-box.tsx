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
    <form onSubmit={submit} role="search" className="search-shell flex w-full items-center gap-2 p-2 focus-within:border-[color:var(--focus)]">
      <MagnifyingGlass size={22} className="ml-2 shrink-0 text-[color:var(--muted)]" aria-hidden="true" />
      <input
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder="搜索产品或交付方式"
        aria-label="搜索产品或交付方式"
        className="min-h-11 min-w-0 flex-1 bg-transparent px-1 outline-none placeholder:text-[color:var(--muted)]/70"
      />
      <button className="button-primary tactile shrink-0">
        查报价 <ArrowRight size={16} weight="bold" />
      </button>
    </form>
  );
}
