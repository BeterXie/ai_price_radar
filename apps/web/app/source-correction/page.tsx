import { SourcePolicyForm } from "@/components/source-policy-form";

export const metadata = {
  title: "报告数据错误 | AI Price Radar",
};

export default function SourceCorrectionPage() {
  return (
    <main className="mx-auto max-w-2xl space-y-6 px-4 py-10">
      <h1 className="text-2xl font-semibold">报告数据错误</h1>
      <p className="text-sm leading-6 text-black/60">
        价格、库存、回源链接或商品归属有误时，请提交纠错请求；管理员会核对公开页面后处理。
      </p>
      <SourcePolicyForm requestType="correction" />
    </main>
  );
}
