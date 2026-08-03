export function GuideSteps({ title, items }: { title?: string; items: readonly string[] }) {
  return (
    <div>
      {title ? <h3 className="text-lg font-semibold">{title}</h3> : null}
      <ol className={title ? "mt-4 space-y-3" : "space-y-3"}>
        {items.map((item, index) => (
          <li key={`${index}-${item}`} className="grid grid-cols-[36px_minmax(0,1fr)] gap-3 rounded-[12px] border hairline bg-[color:var(--panel)] p-4 text-sm leading-6">
            <span className="mono grid size-9 place-items-center rounded-[9px] bg-[color:var(--ink)] text-xs text-white" aria-hidden="true">
              {String(index + 1).padStart(2, "0")}
            </span>
            <span className="pt-1.5">{item}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}
