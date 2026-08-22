import { Check } from "@phosphor-icons/react/ssr";

export function GuideChecklist({ title, items }: { title?: string; items: readonly string[] }) {
  return (
    <div>
      {title ? <h3 className="text-lg font-semibold">{title}</h3> : null}
      <ul className={title ? "mt-4 grid gap-3 sm:grid-cols-2" : "grid gap-3 sm:grid-cols-2"}>
        {items.map((item) => (
          <li key={item} className="flex min-h-11 items-start gap-3 rounded-[9px] border hairline bg-[color:var(--panel)] p-4 text-sm leading-6">
            <span className="mt-0.5 grid size-5 shrink-0 place-items-center rounded-full bg-[color:var(--accent)] text-[color:var(--accent-ink)]">
              <Check size={13} weight="bold" aria-hidden="true" />
            </span>
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
