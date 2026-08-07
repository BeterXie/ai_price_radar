type GuideTocItem = {
  id: string;
  label: string;
};

export function GuideToc({ items, mobile = false }: { items: GuideTocItem[]; mobile?: boolean }) {
  if (mobile) {
    return (
      <nav aria-label="本页目录" className="overflow-x-auto border-y hairline lg:hidden">
        <ol className="flex min-w-max gap-1 py-2">
          {items.map((item) => (
            <li key={item.id}>
              <a href={`#${item.id}`} className="flex min-h-11 items-center rounded-[10px] px-3 text-sm text-black/60 hover:bg-black/5 hover:text-[color:var(--ink)]">
                {item.label}
              </a>
            </li>
          ))}
        </ol>
      </nav>
    );
  }

  return (
    <nav aria-label="本页目录" className="sticky top-24 hidden lg:block">
      <p className="text-sm font-semibold">本页目录</p>
      <ol className="mt-3 border-l hairline">
        {items.map((item) => (
          <li key={item.id}>
            <a href={`#${item.id}`} className="flex min-h-11 items-center border-l border-transparent px-4 text-sm text-black/55 hover:border-black hover:text-black">
              {item.label}
            </a>
          </li>
        ))}
      </ol>
    </nav>
  );
}

export type { GuideTocItem };
