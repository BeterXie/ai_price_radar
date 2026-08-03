import Link from "next/link";
import { BookOpenText } from "@phosphor-icons/react/ssr";

type ContextualGuideLinkProps = {
  href: string;
  title?: string;
  description?: string;
  label?: string;
};

export function ContextualGuideLink({
  href,
  title = "第一次购买这类商品？",
  description = "先了解交付方式、确认步骤和账号安全注意事项。",
  label = "查看使用教程",
}: ContextualGuideLinkProps) {
  return (
    <aside className="rounded-[14px] border hairline bg-[color:var(--panel)] p-5">
      <div className="flex items-start gap-3">
        <BookOpenText size={24} className="mt-0.5 shrink-0" aria-hidden="true" />
        <div>
          <h3 className="font-semibold">{title}</h3>
          <p className="mt-2 text-sm leading-6 text-[color:var(--muted)]">{description}</p>
          <Link href={href} className="tactile mt-4 inline-flex min-h-11 items-center rounded-[10px] bg-[color:var(--ink)] px-4 text-sm font-medium text-white">
            {label}
          </Link>
        </div>
      </div>
    </aside>
  );
}
