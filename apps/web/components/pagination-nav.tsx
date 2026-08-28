import Link from "next/link";

export const DIRECTORY_PAGE_SIZE = 50;

export function parsePage(value: string | undefined): number {
  if (!value || !/^\d+$/.test(value)) return 1;
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : 1;
}

export function getTotalPages(total: number, pageSize = DIRECTORY_PAGE_SIZE): number {
  return Math.max(1, Math.ceil(total / pageSize));
}

export function PaginationNav({
  page,
  totalPages,
  hrefForPage,
  ariaLabel,
}: {
  page: number;
  totalPages: number;
  hrefForPage: (page: number) => string;
  ariaLabel: string;
}) {
  if (totalPages <= 1) return null;

  return (
    <nav className="mt-6 flex items-center justify-between text-sm" aria-label={ariaLabel}>
      {page > 1 ? <Link href={hrefForPage(page - 1)} className="underline hover:no-underline">上一页</Link> : <span className="text-black/30">上一页</span>}
      <span className="text-black/50">第 {page} / {totalPages} 页</span>
      {page < totalPages ? <Link href={hrefForPage(page + 1)} className="underline hover:no-underline">下一页</Link> : <span className="text-black/30">下一页</span>}
    </nav>
  );
}
