import { ArrowSquareOut } from "@phosphor-icons/react";
import { DemoIframe } from "./demo-iframe";

const SAMPLES = [
  {
    name: "GPT-6.2 Astra",
    label: "本次样本 · 鹈鹕兜风",
    url: "/demos/benchmarks/pelican-gpt62-astra.html",
  },
  {
    name: "GPT-6 Astra",
    label: "旧文样本 · 鹈鹕的海边骑行",
    url: "/demos/benchmarks/pelican-gpt6-astra-full.html",
  },
];

export function PelicanAstraComparison() {
  return (
    <section className="mt-8" aria-labelledby="pelican-comparison-title">
      <h2 id="pelican-comparison-title" className="text-lg font-bold text-[color:var(--foreground)]">
        GPT-6.2 Astra vs GPT-6 Astra
      </h2>
      <p className="mt-1 text-sm text-[color:var(--muted)]">
        两份动画都可以独立暂停。先看脚和踏板，再看羽毛、车架与背景。
      </p>
      <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
        {SAMPLES.map((sample) => (
          <div key={sample.url} className="min-w-0 rounded-xl border border-[color:var(--line)] bg-[color:var(--panel)] p-3 sm:p-4">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <div>
                <h3 className="text-base font-bold text-[color:var(--foreground)]">{sample.name}</h3>
                <p className="mt-1 text-xs text-[color:var(--muted)]">{sample.label}</p>
              </div>
              <a
                href={sample.url}
                target="_blank"
                rel="noreferrer"
                className="pelican-article-action"
                aria-label={`单独打开 ${sample.name} 鹈鹕动画`}
              >
                单独打开
                <ArrowSquareOut size={13} />
              </a>
            </div>
            <div className="aspect-[10/9] min-h-[440px] w-full overflow-hidden rounded-lg border border-[color:var(--line)]">
              <DemoIframe src={sample.url} title={`${sample.name} 鹈鹕动画`} />
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
