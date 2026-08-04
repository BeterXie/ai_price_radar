import { SourcePolicyForm } from "@/components/source-policy-form";

export const metadata = {
  title: "申请停止收录 | AI Price Radar",
};

export default function SourceOptOutPage() {
  return (
    <main className="mx-auto max-w-2xl space-y-6 px-4 py-10">
      <h1 className="text-2xl font-semibold">申请停止收录</h1>
      <p className="text-sm leading-6 text-black/60">
        如果你是来源所有者，提交后我们会立即对该来源暂停采集（最长 7 天等待核实），核实通过后永久退出收录并从公开目录下架。
      </p>
      <SourcePolicyForm requestType="opt_out" />
    </main>
  );
}
