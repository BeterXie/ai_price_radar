import Link from "next/link";
import { ArrowRight, ArrowUpRight } from "@phosphor-icons/react/ssr";
import { RelayHealthStatus } from "@/components/relay-health";
import { RelayStationIcon } from "@/components/relay-station-icon";
import { getRelayStations } from "@/lib/api";
import type { RelayStationListOut } from "@/lib/types";

export function HomeRelayPreview({ data = null, loading = false }: { data?: RelayStationListOut | null; loading?: boolean }) {
  if (data?.enabled === false) return null;
  // The public API owns directory ordering, including sponsored placement.
  // Keep that order; these positions are not a performance leaderboard.
  const stations = data?.items.slice(0, 3) || [];

  return (
    <section className="home-relays shell" aria-labelledby="home-relays-title">
      <div className="home-section-heading">
        <div className="home-relay-heading">
          <h2 id="home-relays-title">中转站</h2>
          {stations.length > 0 ? <span title="与中转站目录顺序一致：赞助优先，其余按运营者设置排序。">目录前三</span> : null}
        </div>
        <Link href="/relays" className="text-action">全部中转站 <ArrowRight size={18} aria-hidden="true" /></Link>
      </div>
      {stations.length ? (
        <ol className="home-relay-list">
          {stations.map((station, index) => {
            const health = station.health;
            const cacheSamples = health?.cache_sample_count_24h || 0;
            const cacheRate = cacheSamples > 0 && cacheSamples < 3
              ? "样本不足"
              : cacheSamples >= 3 && health?.cache_hit_rate_24h != null ? `${health.cache_hit_rate_24h}%` : "暂无数据";
            const availability = health?.sample_count_7d && health.availability_7d != null ? `${health.availability_7d}%` : "暂无数据";
            return (
              <li key={station.id}>
                <Link href={`/relays#relay-${station.id}`} className="home-relay-card" aria-label={`目录第 ${index + 1} 位：${station.name}，查看检测详情`}>
                  <div className="home-relay-identity">
                    <span className="home-relay-rank" aria-hidden="true">{String(index + 1).padStart(2, "0")}</span>
                    <RelayStationIcon id={station.id} name={station.name} website={station.url} />
                    <h3>{station.name}</h3>
                    {station.is_sponsored ? <span className="ad-badge">赞助</span> : null}
                    <ArrowUpRight size={17} className="home-relay-arrow" aria-hidden="true" />
                  </div>
                  <dl className="home-relay-metrics">
                    <div><dt>可用率 · 7天</dt><dd>{availability}</dd></div>
                    <div title="近24小时重复输入缓存率，先排除零命中，再各去掉一个最高值和最低值后取平均；至少3个非零有效样本。"><dt>缓存率 · 24h</dt><dd>{cacheRate}</dd></div>
                  </dl>
                  <div className="home-relay-state">
                    <span className="home-relay-model" title={health?.probe_model || undefined}>{health?.probe_model || "未设置检测模型"}</span>
                    <RelayHealthStatus health={health} />
                  </div>
                </Link>
              </li>
            );
          })}
        </ol>
      ) : (
        <div className="home-relay-empty" role="status">
          <p>{loading ? "正在读取中转站…" : data ? "暂无已收录中转站" : "中转站暂时无法加载"}</p>
          {data && !loading ? <Link href="/shops/submit?type=relay" className="text-action">申请收录 <ArrowRight size={16} aria-hidden="true" /></Link> : null}
        </div>
      )}
    </section>
  );
}

export async function HomeRelays() {
  const data = await getRelayStations().catch(() => null);
  return <HomeRelayPreview data={data} />;
}
