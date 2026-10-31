"use client";

import { FormEvent, useEffect, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, CircleNotch, MagnifyingGlass, X } from "@phosphor-icons/react";
import { buildSearchHref, normalizeSearchQuery } from "@/lib/search";

export function SearchBox({
  defaultValue = "", filters = {}, action = "/products", compact = false,
  placeholder = "搜索商品、品牌或店铺",
}: {
  defaultValue?: string;
  filters?: Record<string, string>;
  action?: string;
  compact?: boolean;
  placeholder?: string;
}) {
  const [value, setValue] = useState(defaultValue);
  const [pending, startTransition] = useTransition();
  const router = useRouter();
  useEffect(() => setValue(defaultValue), [defaultValue]);

  function search(nextValue: string) {
    const query = normalizeSearchQuery(nextValue);
    setValue(query);
    startTransition(() => router.push(buildSearchHref(action, query, filters), { scroll: !compact }));
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    search(value);
  }
  return (
    <form action={action} method="get" onSubmit={submit} role="search" aria-label={placeholder} aria-busy={pending} className={`search-shell flex w-full items-center gap-2 p-2 focus-within:border-[color:var(--focus)]${compact ? " search-shell-compact" : ""}`}>
      {Object.entries(filters).filter(([name, value]) => value && !["q", "page", "offset", "snapshot"].includes(name)).map(([name, value]) => <input key={name} type="hidden" name={name} value={value} />)}
      <MagnifyingGlass size={compact ? 18 : 22} className="ml-2 shrink-0 text-[color:var(--muted)]" aria-hidden="true" />
      <input
        type="search"
        name="q"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && (event.nativeEvent.isComposing || event.keyCode === 229)) event.preventDefault();
        }}
        placeholder={placeholder}
        aria-label={placeholder}
        autoComplete="off"
        enterKeyHint="search"
        maxLength={100}
        className="min-h-11 min-w-0 flex-1 bg-transparent px-1 outline-none placeholder:text-[color:var(--muted)]/70"
      />
      {value ? <button type="button" onClick={() => search("")} className="search-clear" aria-label="清除搜索关键词" disabled={pending}><X size={16} aria-hidden="true" /></button> : null}
      <button type="submit" className="button-primary tactile shrink-0" disabled={pending}>
        {pending ? <><CircleNotch size={16} className="motion-safe:animate-spin" aria-hidden="true" />搜索中</> : compact ? "搜索" : <>查报价 <ArrowRight size={16} weight="bold" /></>}
      </button>
    </form>
  );
}
