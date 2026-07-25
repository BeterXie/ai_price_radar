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
    <form onSubmit={submit} className="flex w-full items-center gap-3 rounded-[18px] border border-black/15 bg-white p-2 shadow-[0_18px_50px_rgba(20,22,16,.08)]">
      <MagnifyingGlass size={22} className="ml-3 shrink-0 text-black/45" />
      <input
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder="搜索 Free、Plus、K12、Pro 5x、Pro 20x…"
        aria-label="搜索产品"
        className="min-w-0 flex-1 bg-transparent px-1 py-3 outline-none placeholder:text-black/35"
      />
      <button className="tactile flex shrink-0 items-center gap-2 rounded-[12px] bg-[color:var(--ink)] px-5 py-3 text-sm font-medium text-white">
        搜索 <ArrowRight size={16} weight="bold" />
      </button>
    </form>
  );
}
