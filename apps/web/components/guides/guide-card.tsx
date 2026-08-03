import Link from "next/link";
import { ArrowRight } from "@phosphor-icons/react/ssr";

type GuideCardProps = {
  href: string;
  title: string;
  description: string;
  meta?: string;
};

export function GuideCard({ href, title, description, meta }: GuideCardProps) {
  return (
    <Link
      href={href}
      className="tactile group flex min-h-44 flex-col justify-between rounded-[14px] border hairline bg-[color:var(--panel)] p-5 hover:border-black focus-visible:border-black"
    >
      <div>
        {meta ? <p className="mono text-xs text-[color:var(--muted)]">{meta}</p> : null}
        <h3 className="mt-2 text-lg font-semibold tracking-[-.025em]">{title}</h3>
        <p className="mt-3 text-sm leading-6 text-[color:var(--muted)]">{description}</p>
      </div>
      <span className="mt-5 flex min-h-11 items-center gap-2 text-sm font-medium">
        查看教程
        <ArrowRight size={17} className="transition-transform group-hover:translate-x-1" aria-hidden="true" />
      </span>
    </Link>
  );
}
