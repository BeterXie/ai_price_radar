import type { Metadata } from "next";
import { InfoPage, SectionIntro } from "@/components/page-shell";

export const metadata: Metadata = { title: "开发者与数据接入", description: "公开 API、Atom Feed、商家 JSON Feed 与 Connector 接入说明。", alternates: { canonical: "/developers" } };
const endpoints = [
  ["GET /api/v1/products", "标准产品卡片、近期有货观测价、官方价格参考与信息覆盖情况。"],
  ["GET /api/v1/catalog/groups", "跨产品同款报价目录，支持交付、期限、质保、库存、更新时间和价格区间筛选。"],
  ["GET /api/v1/products/{slug}", "产品详情、同款报价、90 天聚合价格与库存趋势。"],
  ["GET /api/v1/corrections", "已解决且允许公开的纠错摘要，不返回联系方式和原始私密内容。"],
  ["GET /api/v1/watch.atom", "无需账号的价格与补货 Atom Feed。"],
];

export default function DevelopersPage() {
  return (
    <InfoPage eyebrow="开发者资料" title="开发者与数据接入" description="提供只读公开 API、Atom 订阅、LDXP Connector 和商家 JSON Feed。接口不承诺商业 SLA，请使用缓存并控制请求频率。">
      <section>
        <SectionIntro title="公开 API" description="接口与公开目录使用同一批已发布数据。客户端需要处理超时、空结果和字段调整。" />
        <div className="data-table-frame mt-6 overflow-hidden border border-[color:var(--line-strong)] bg-[color:var(--panel)]" data-vds-layer="evidence">
          {endpoints.map(([method, copy]) => <div key={method} className="grid gap-2 border-b border-[color:var(--line)] p-5 last:border-b-0 md:grid-cols-[280px_1fr]"><code className="mono text-sm font-semibold text-[color:var(--info)]">{method}</code><p className="text-sm leading-6 text-[color:var(--muted)]">{copy}</p></div>)}
        </div>
      </section>
      <section className="data-table-frame mt-12 grid gap-px overflow-hidden border border-[color:var(--line-strong)] bg-[color:var(--line)] md:grid-cols-2" data-vds-layer="evidence">
        <div className="bg-[color:var(--panel)] p-6"><h2 className="text-2xl font-semibold">商家 JSON Feed</h2><p className="mt-3 text-sm leading-7 text-[color:var(--muted)]">Feed 可返回商品数组，或包含 shop、updated_at、items 的对象。商品至少提供稳定 ID、名称和来源 URL；价格、库存、类别与公开描述按统一导入模型处理。</p><a href="/shops/submit" className="button-primary mt-6">提交 Feed 地址</a></div>
        <div className="bg-[color:var(--panel)] p-6"><h2 className="text-2xl font-semibold">Connector 接入</h2><p className="mt-3 text-sm leading-7 text-[color:var(--muted)]">后端 Connector 接口统一输出标准化记录。新增来源应实现读取、校验和转换，不直接写业务数据库；发布流程继续使用幂等导入和原子快照。</p><a href="https://github.com/BeterXie/ai_price_radar/tree/main/pipeline/connectors" target="_blank" rel="noreferrer" className="button-secondary mt-6">查看 Connector 代码</a></div>
      </section>
    </InfoPage>
  );
}
