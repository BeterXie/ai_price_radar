import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowSquareOut, CheckCircle, EnvelopeSimple, Lightning, ShieldCheck, Tag, Users } from "@phosphor-icons/react/ssr";
import { InfoPage, SectionIntro } from "@/components/page-shell";
import { BUSINESS_EMAIL } from "@/lib/community";
import { getMeta } from "@/lib/api";

export const metadata: Metadata = {
  title: "商务合作 / 广告投放",
  description: "面向 AI 账号发卡平台、中转 API 服务商、合租拼车平台及相关工具团队，提供精准高转化的商业推广与合作曝光渠道。",
  alternates: { canonical: "/advertise" },
  openGraph: {
    title: "商务合作 / 广告投放 · AI Price Radar",
    description: "面向 AI 订阅与账号服务商，提供分类置顶、CPS 返利、专属优惠码与品牌赞助渠道。",
    url: "/advertise",
  },
};

const valuePoints = [
  {
    Icon: Users,
    title: "超高转化交易流量",
    copy: "访问 AI Price Radar 的用户均带有明确的购买与比价意向，涵盖开发者、企业白领与 AI 高频用户，转化率远超普通泛流量。",
  },
  {
    Icon: Lightning,
    title: "热门品类精准覆盖",
    copy: "深度聚焦 ChatGPT Plus 充值/独享、Pro 拼车 (5x/20x)、Claude Pro、Grok Super、API 中转等全网最核心的 AI 消费场景。",
  },
  {
    Icon: ShieldCheck,
    title: "客观公信力背书",
    copy: "坚持中立透明的报价监控与真实来源核验，平台积累了极佳的用户口碑与复访黏性，商家曝光更具信任感。",
  },
];

const cooperationModels = [
  {
    title: "核心品类置顶推荐位",
    desc: "在 ChatGPT Plus、Grok Super、Pro 拼车等高访问量品类顶部提供专属推荐位，附带清晰的 [赞助] 标识，获得全站最大的商业曝光与直接进店点击。",
    badge: "最高曝光",
  },
  {
    title: "CPS 联盟返利 & 专属优惠码",
    desc: "为本站用户提供专属折扣码（如立减或折扣优惠券），通过独家追踪链接按真实成交流水结算佣金分成，实现零风险品效合一。",
    badge: "效果计费",
  },
  {
    title: "中转 API 与开发者服务赞助",
    desc: "面向开发者与高频 API 采购用户，在开发者接口、工具页或首页推荐位进行中转分发平台的专属品牌赞助与流量导入。",
    badge: "精准导流",
  },
  {
    title: "优质店铺认证与快速采集",
    desc: "为长期稳定的优质店铺提供专属认证主页、优先自动采集与高频刷新支持，确保商品上架后以最快速度展示给全网买家。",
    badge: "长期合作",
  },
];

const standards = [
  ["店铺运营稳定", "合作商家需具备至少 1~3 个月的稳定运营记录，拥有健全的售后服务与客服通道，拒绝无售后保障的短期商户。"],
  ["商品信息真实", "报价、库存及交付模式必须与实际一致，严禁虚标库存、诱导跳价或恶意欺诈。一旦核实严重客诉将立即终止合作。"],
  ["赞助透明规范", "所有付费推广与推荐商品必须明确带有 [赞助] 或 [推广] 标识，不篡改、不伪造客观自然比价算法与真实最低价。"],
] as const;

export default async function AdvertisePage() {
  const meta = await getMeta().catch(() => null);
  if (!meta?.advertise_enabled) {
    notFound();
  }

  const mailtoUrl = `mailto:${BUSINESS_EMAIL}?subject=${encodeURIComponent("商务合作咨询 - AI Price Radar")}`;

  return (
    <InfoPage
      eyebrow="商业化与合作"
      title="商务合作 / 广告投放"
      description="面向 AI 账号发卡平台、中转 API 服务商、拼车合租平台及相关工具团队，提供精准、高转化、高意向的商业推广与合作曝光渠道。"
    >
      {/* 核心优势 */}
      <section>
        <SectionIntro
          title="为什么选择在 AI Price Radar 投放？"
          description="我们的受众群体极其聚焦，每一个点击都代表一次潜在的真实订单交易。"
        />
        <div className="mt-8 grid gap-5 sm:grid-cols-3">
          {valuePoints.map(({ Icon, title, copy }) => (
            <div key={title} className="rounded-[16px] border border-[color:var(--line)] bg-[color:var(--panel)] p-6 shadow-sm">
              <div className="flex h-11 w-11 items-center justify-center rounded-[12px] bg-[color:var(--surface)] text-[color:var(--ink)]">
                <Icon size={24} weight="duotone" />
              </div>
              <h3 className="mt-4 text-base font-semibold text-[color:var(--ink)]">{title}</h3>
              <p className="mt-2 text-sm leading-6 text-[color:var(--muted)]">{copy}</p>
            </div>
          ))}
        </div>
      </section>

      {/* 合作模式 */}
      <section className="mt-14 sm:mt-18">
        <SectionIntro
          title="多样化的合作模式"
          description="支持灵活定制的曝光与结算机制，帮助您的店铺与服务迅速扩大市场份额。"
        />
        <div className="mt-8 grid gap-4 sm:grid-cols-2">
          {cooperationModels.map(({ title, desc, badge }) => (
            <div key={title} className="flex flex-col justify-between rounded-[16px] border border-[color:var(--line)] bg-[color:var(--panel)] p-6">
              <div>
                <div className="flex items-center justify-between gap-3">
                  <h3 className="text-base font-semibold text-[color:var(--ink)]">{title}</h3>
                  <span className="rounded-full bg-[color:var(--surface)] px-2.5 py-0.5 text-xs font-medium text-[color:var(--muted)]">
                    {badge}
                  </span>
                </div>
                <p className="mt-3 text-sm leading-6 text-[color:var(--muted)]">{desc}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* 准入原则 */}
      <section className="mt-14 sm:mt-18">
        <SectionIntro
          title="合作准入与合规原则"
          description="为保护平台长期公信力与广大用户的消费安全，所有商务合作均需遵循以下基准："
        />
        <div className="mt-6 border-t border-[color:var(--line-strong)]">
          {standards.map(([title, copy]) => (
            <div key={title} className="grid gap-2 border-b border-[color:var(--line)] py-5 md:grid-cols-[220px_1fr]">
              <h3 className="text-sm font-semibold text-[color:var(--ink)]">{title}</h3>
              <p className="text-sm leading-6 text-[color:var(--muted)]">{copy}</p>
            </div>
          ))}
        </div>
      </section>

      {/* 联系方式与 CTA */}
      <section className="mt-14 sm:mt-18">
        <div className="rounded-[20px] border border-[color:var(--line-strong)] bg-[color:var(--panel)] p-8 sm:p-10">
          <div className="max-w-2xl">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-[color:var(--surface)] px-3 py-1 text-xs font-medium text-[color:var(--muted)]">
              <EnvelopeSimple size={14} /> 官方联络渠道
            </span>
            <h2 className="mt-4 text-2xl font-bold tracking-tight text-[color:var(--ink)] sm:text-3xl">
              立即开启商务合作
            </h2>
            <p className="mt-3 text-sm leading-7 text-[color:var(--muted)]">
              如有意向开展品类置顶推荐、CPS 返利优惠码合作或品牌赞助，请发送邮件至我们的商务邮箱。我们通常会在 1 个工作日内回复并沟通合作方案。
            </p>

            <div className="mt-6 flex flex-wrap items-center gap-4">
              <a
                href={mailtoUrl}
                className="button-primary inline-flex items-center gap-2"
              >
                <EnvelopeSimple size={18} /> 发送邮件咨询
              </a>
              <span className="mono text-sm font-semibold text-[color:var(--ink)]">
                {BUSINESS_EMAIL}
              </span>
            </div>

            <div className="mt-8 rounded-[12px] bg-[color:var(--surface)] p-4 text-xs leading-6 text-[color:var(--muted)]">
              <p className="font-semibold text-[color:var(--ink)]">💡 来信建议附带以下信息，以便我们更高效地推进：</p>
              <ul className="mt-1 list-disc pl-5">
                <li>店铺 / 平台名称及公开访问网址</li>
                <li>主营商品或服务类型（例如：ChatGPT Plus 充值、Pro 拼车合租、中转 API 等）</li>
                <li>期望的合作形式（品类置顶、CPS 专属折扣码、长期赞助等）</li>
                <li>您的有效沟通联系方式（Telegram、微信或直接邮箱回复）</li>
              </ul>
            </div>
          </div>
        </div>

        <div className="mt-8 flex flex-wrap gap-3 border-t border-[color:var(--line-strong)] pt-8">
          <Link href="/shops/submit" className="button-secondary">免费提交店铺收录</Link>
          <Link href="/about" className="button-secondary">了解平台理念</Link>
        </div>
      </section>
    </InfoPage>
  );
}
