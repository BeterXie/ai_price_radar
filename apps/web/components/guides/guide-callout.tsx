import type { ReactNode } from "react";
import { Info, ShieldWarning, WarningCircle } from "@phosphor-icons/react/ssr";

type Tone = "info" | "warning" | "danger" | "success";

const toneStyles: Record<Tone, string> = {
  info: "border-[color:var(--info)]/25 bg-[color:var(--info-soft)]",
  warning: "border-[color:var(--warning)]/30 bg-[color:var(--warning-soft)]",
  danger: "border-[color:var(--danger)]/30 bg-[color:var(--danger-soft)]",
  success: "border-[color:var(--success)]/25 bg-[color:var(--success-soft)]",
};

export function GuideCallout({ tone = "info", title, children }: { tone?: Tone; title: string; children: ReactNode }) {
  const Icon = tone === "info" || tone === "success" ? Info : tone === "danger" ? ShieldWarning : WarningCircle;
  return (
    <aside className={`rounded-[9px] border p-5 ${toneStyles[tone]}`}>
      <div className="flex items-start gap-3">
        <Icon size={22} className="mt-0.5 shrink-0" aria-hidden="true" />
        <div>
          <h3 className="font-semibold">{title}</h3>
          <div className="mt-2 text-sm leading-6 text-black/65">{children}</div>
        </div>
      </div>
    </aside>
  );
}
