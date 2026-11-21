import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowClockwise } from "@phosphor-icons/react/ssr";
import { AlertBoard } from "@/components/alert-board";
import { AlertRefresh } from "@/components/alert-refresh";
import { ALERT_VIEWS, alertTime, alertView, currentAlertRows } from "@/lib/alert-report";
import { getLatestAlertReport } from "@/lib/alert-report-server";
import { SITE_URL } from "@/lib/site";
import { IS_PRIMARY_SITE } from "@/lib/brands";

export const dynamic = "force-dynamic";
type Props = { searchParams: Promise<Record<string, string | string[] | undefined>> };

export async function generateMetadata({ searchParams }: Props): Promise<Metadata> {
  if (!IS_PRIMARY_SITE) notFound();
  const view = alertView((await searchParams).view);
  const title = ALERT_VIEWS.find((item) => item.key === view)!.label;
  return { title: `${title} · 最新 AI 商品报价`, description: "查看最新一轮降价、涨价与低价 Team 车提醒。同名商品保留最低价，自动过滤已结束的 Team 车。", alternates: { canonical: `${SITE_URL}/alerts?view=${view}` } };
}

export default async function AlertsPage({ searchParams }: Props) {
  if (!IS_PRIMARY_SITE) notFound();
  const view = alertView((await searchParams).view);
  let failed = false;
  const report = await getLatestAlertReport().catch(() => { failed = true; return null; });
  const initialNow = Date.now();
  const visibleReport = report ? { ...report, drops: currentAlertRows(report, "drops", initialNow),
    rises: currentAlertRows(report, "rises", initialNow), team: currentAlertRows(report, "team", initialNow) } : null;
  const title = ALERT_VIEWS.find((item) => item.key === view)!.label;
  return <main id="main-content" className="shell alert-page">
    <AlertRefresh />
    <header className="alert-page-header">
      <div><p className="alert-eyebrow">最新报价动态</p><h1>{title}</h1>
        <p className="alert-page-summary">{view === "team" ? "找一班合适的 Team 车。" : view === "drops" ? "这轮更新，哪些商品便宜了。" : "这轮更新，哪些商品涨价了。"}</p></div>
      <div className="alert-updated">{report && <time dateTime={report.published_at}>{alertTime(report.published_at)} 更新 · 北京时间</time>}
        <a className="text-action" href={`/alerts?view=${view}`}><ArrowClockwise size={17} aria-hidden="true" />刷新报价</a></div>
    </header>
    {visibleReport ? <AlertBoard report={visibleReport} view={view} initialNow={initialNow} /> : <div className="alert-empty" role="status">
      <h2>{failed ? "提醒榜暂时加载失败" : "提醒榜正在等待首次更新"}</h2><p>{failed ? "稍后刷新重试，也可以先查看全部商品报价。" : "下一次报价同步完成后，这里会显示最新提醒。"}</p>
      <Link href="/products" className="button-secondary">查看全部报价</Link>
    </div>}
  </main>;
}
