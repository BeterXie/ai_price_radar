export type GuideFaqItem = {
  question: string;
  answer: string;
};

export function GuideFaq({ items }: { items: readonly GuideFaqItem[] }) {
  return (
    <div className="space-y-3">
      {items.map((item) => (
        <details key={item.question} className="group rounded-[12px] border hairline bg-[color:var(--panel)] open:border-black">
          <summary className="flex min-h-14 cursor-pointer list-none items-center justify-between gap-4 px-5 py-3 font-semibold marker:content-none">
            {item.question}
            <span className="text-xl font-normal text-black/45 group-open:rotate-45" aria-hidden="true">+</span>
          </summary>
          <p className="border-t hairline px-5 py-4 text-sm leading-7 text-black/65">{item.answer}</p>
        </details>
      ))}
    </div>
  );
}
