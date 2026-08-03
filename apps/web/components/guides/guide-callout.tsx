import type { ReactNode } from "react";
import { Info, ShieldWarning, WarningCircle } from "@phosphor-icons/react/ssr";

type Tone = "info" | "warning" | "danger" | "success";

const toneStyles: Record<Tone, string> = {
  info: "border-black/20 bg-black/[.035]",
  warning: "border-[#94751d]/35 bg-[#efe5bd]/45",
  danger: "border-[color:var(--danger)]/35 bg-[#ead8d4]/45",
  success: "border-[#4e6c2d]/35 bg-[#dfe8d1]/55",
};

export function GuideCallout({ tone = "info", title, children }: { tone?: Tone; title: string; children: ReactNode }) {
  const Icon = tone === "info" || tone === "success" ? Info : tone === "danger" ? ShieldWarning : WarningCircle;
  return (
    <aside className={`rounded-[14px] border p-5 ${toneStyles[tone]}`}>
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
