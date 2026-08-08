import { ArrowSquareOut, CheckCircle, Lifebuoy } from "@phosphor-icons/react/ssr";
import type { GuideWalkthrough as GuideWalkthroughData } from "@/lib/guides/types";

export function GuideWalkthrough({ walkthrough }: { walkthrough: GuideWalkthroughData }) {
  return (
    <div className="space-y-5">
      <div>
        <h3 className="text-xl font-semibold tracking-[-.025em]">{walkthrough.title}</h3>
        <p className="mt-2 text-sm leading-7 text-black/65">{walkthrough.intro}</p>
      </div>

      <ol className="space-y-4">
        {walkthrough.steps.map((step, index) => (
          <li key={step.title} className="overflow-hidden rounded-[16px] border border-[color:var(--line-strong)] bg-[color:var(--panel)]">
            <div className="grid gap-4 p-5 sm:grid-cols-[44px_minmax(0,1fr)] sm:p-6">
              <span className="mono grid size-11 place-items-center rounded-[11px] bg-[color:var(--ink)] text-sm text-white" aria-hidden="true">
                {String(index + 1).padStart(2, "0")}
              </span>
              <div>
                <h4 className="text-lg font-semibold">{step.title}</h4>
                <p className="mt-3 text-sm leading-7 text-black/75">{step.action}</p>

                {step.items?.length ? (
                  <ul className="mt-4 space-y-2 text-sm leading-6 text-black/75">
                    {step.items.map((item) => (
                      <li key={item} className="flex gap-3">
                        <span className="mono shrink-0 text-black/40" aria-hidden="true">→</span>
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                ) : null}

                {step.links?.length ? (
                  <div className="mt-4 flex flex-wrap gap-2">
                    {step.links.map((link) => (
                      <a
                        key={link.url}
                        href={link.url}
                        target={link.url.startsWith("https://") ? "_blank" : undefined}
                        rel={link.url.startsWith("https://") ? "noreferrer" : undefined}
                        className="inline-flex min-h-11 items-center gap-2 rounded-[10px] border border-[color:var(--line-strong)] px-3 text-sm font-semibold hover:bg-black hover:text-white"
                      >
                        {link.label}
                        <ArrowSquareOut size={16} aria-hidden="true" />
                      </a>
                    ))}
                  </div>
                ) : null}

                <div className="mt-4 flex items-start gap-3 border-t hairline pt-4 text-sm leading-6">
                  <CheckCircle size={20} weight="fill" className="mt-0.5 shrink-0 text-[color:var(--accent-ink)]" aria-hidden="true" />
                  <p><strong>完成标志：</strong>{step.result}</p>
                </div>

                {step.trouble ? (
                  <div className="mt-3 flex items-start gap-3 rounded-[10px] bg-black/[.045] p-3 text-sm leading-6 text-black/70">
                    <Lifebuoy size={20} className="mt-0.5 shrink-0" aria-hidden="true" />
                    <p><strong>卡住了：</strong>{step.trouble}</p>
                  </div>
                ) : null}
              </div>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
