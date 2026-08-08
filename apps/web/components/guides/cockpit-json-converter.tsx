"use client";

import { useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  ArrowSquareOut,
  CheckCircle,
  DownloadSimple,
  FileJs,
  ShieldCheck,
  Trash,
  UploadSimple,
  Warning,
} from "@phosphor-icons/react";
import {
  buildCockpitDocument,
  COCKPIT_LIMITS,
  convertJsonDocuments,
  convertJsonTexts,
  parseJsonText,
  type CockpitConversionIssue,
  type CockpitConversionResult,
  type JsonDocument,
  type JsonTextDocument,
} from "@/lib/guides/cockpit-converter";

function maskEmail(email: string | undefined): string {
  if (!email || !email.includes("@")) return email || "未识别";
  const [name, domain] = email.split("@");
  return `${name.slice(0, 2)}***@${domain}`;
}

function downloadName(): string {
  const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
  return `cockpit-import-${timestamp}.json`;
}

export function CockpitJsonConverter() {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [inputText, setInputText] = useState("");
  const [selectedFiles, setSelectedFiles] = useState<readonly string[]>([]);
  const [result, setResult] = useState<CockpitConversionResult>({ accounts: [], issues: [] });
  const [error, setError] = useState("");
  const [fileSummary, setFileSummary] = useState("");

  const outputText = useMemo(() => {
    if (!result.accounts.length) return "";
    return JSON.stringify(buildCockpitDocument(result.accounts), null, 2);
  }, [result.accounts]);

  function applyConversion(documents: readonly JsonDocument[]): void {
    const nextResult = convertJsonDocuments(documents);
    setResult(nextResult);
    setError(nextResult.accounts.length ? "" : nextResult.issues[0]?.reason || "没有找到可转换账号");
  }

  function convertPastedJson(): void {
    if (!inputText.trim()) {
      setError("请粘贴 JSON，或先选择一个或多个 JSON 文件。");
      return;
    }
    try {
      applyConversion([{ sourceName: "粘贴内容", value: parseJsonText(inputText) }]);
      setSelectedFiles([]);
      setFileSummary("");
    } catch (conversionError) {
      setResult({ accounts: [], issues: [] });
      setError(conversionError instanceof Error ? conversionError.message : "JSON 转换失败");
    }
  }

  async function convertFiles(files: FileList | null): Promise<void> {
    if (!files?.length) return;
    const allFiles = Array.from(files);
    const inScopeFiles = allFiles.slice(0, COCKPIT_LIMITS.maxFilesPerBatch);
    const overflowFiles = allFiles.slice(COCKPIT_LIMITS.maxFilesPerBatch);
    const textDocuments: JsonTextDocument[] = [];
    const fileIssues: CockpitConversionIssue[] = [];
    let totalBytes = 0;

    for (const file of inScopeFiles) {
      if (file.size > COCKPIT_LIMITS.maxFileBytes) {
        fileIssues.push({
          sourceName: file.name,
          path: "$",
          reason: `文件超过 ${COCKPIT_LIMITS.maxFileBytes / (1024 * 1024)} MB 上限`,
        });
        continue;
      }
      if (totalBytes + file.size > COCKPIT_LIMITS.maxTotalFileBytes) {
        fileIssues.push({
          sourceName: file.name,
          path: "$",
          reason: `累计文件大小超过 ${COCKPIT_LIMITS.maxTotalFileBytes / (1024 * 1024)} MB 上限`,
        });
        continue;
      }
      totalBytes += file.size;
      try {
        textDocuments.push({ sourceName: file.name, text: await file.text() });
      } catch (readError) {
        fileIssues.push({
          sourceName: file.name,
          path: "$",
          reason: readError instanceof Error ? readError.message : "文件读取失败",
        });
      }
    }
    for (const file of overflowFiles) {
      fileIssues.push({
        sourceName: file.name,
        path: "$",
        reason: `超过单次 ${COCKPIT_LIMITS.maxFilesPerBatch} 个文件上限`,
      });
    }

    const nextResult = convertJsonTexts(textDocuments);
    setResult({ accounts: nextResult.accounts, issues: [...nextResult.issues, ...fileIssues] });
    setInputText("");
    setSelectedFiles(nextResult.parsedFileNames);
    setFileSummary(`解析文件：${nextResult.parsedFileNames.length} 个成功，${allFiles.length - nextResult.parsedFileNames.length} 个跳过`);
    setError(
      nextResult.accounts.length
        ? ""
        : (nextResult.issues[0] || fileIssues[0])?.reason || "没有找到可转换账号",
    );
  }

  function clearAll(): void {
    setInputText("");
    setSelectedFiles([]);
    setResult({ accounts: [], issues: [] });
    setError("");
    setFileSummary("");
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  function downloadOutput(): void {
    if (!outputText) return;
    const url = URL.createObjectURL(new Blob([outputText], { type: "application/json;charset=utf-8" }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = downloadName();
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <main id="main-content" className="shell py-5 sm:py-8">
      <header className="page-hero !pt-6">
        <Link href="/guides/products/codex-access" className="inline-flex min-h-11 items-center gap-2 text-sm font-semibold hover:underline">
          <ArrowLeft size={18} aria-hidden="true" />
          返回 Codex 教程
        </Link>
        <p className="eyebrow mt-5"><span className="signal-dot" aria-hidden="true" />浏览器本地工具</p>
        <h1 className="page-title mt-5">JSON 转 Cockpit</h1>
        <p className="lede mt-5">
          把常见 ChatGPT Session、CPA、Sub2、Codex auth.json 等账号 JSON 转成 Cockpit Tools 可导入的格式。支持粘贴 JSON 或批量选择文件。
        </p>
      </header>

      <section className="data-strip mt-6 sm:grid-cols-3" aria-label="隐私说明">
        {[
          { title: "只在浏览器解析", copy: "转换逻辑在当前页面运行，不调用上传 API。" },
          { title: "不写入站内存储", copy: "不写数据库、Cookie、localStorage 或分析事件。" },
          { title: "关闭即可清除", copy: "转换内容只保留在当前页面内存中。" },
        ].map(({ title, copy }) => (
          <div key={title} className="data-cell">
            <ShieldCheck size={22} weight="fill" className="text-[color:var(--brand)]" aria-hidden="true" />
            <h2 className="mt-3 font-semibold">{title}</h2>
            <p className="mt-2 text-sm leading-6 text-black/60">{copy}</p>
          </div>
        ))}
      </section>

      <div className="mt-8 grid items-start gap-5 xl:grid-cols-2">
        <section className="rounded-[14px] border border-[color:var(--line-strong)] bg-[color:var(--panel)] p-5 sm:p-6" aria-labelledby="converter-input-title">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="mono text-xs text-black/45">01 / 输入</p>
              <h2 id="converter-input-title" className="mt-2 text-2xl font-semibold tracking-[-.035em]">选择文件或粘贴 JSON</h2>
            </div>
            <button type="button" onClick={clearAll} className="inline-flex min-h-11 items-center gap-2 text-sm font-semibold hover:underline">
              <Trash size={17} aria-hidden="true" />
              清空
            </button>
          </div>

          <div className="mt-5 rounded-[12px] border border-[color:var(--danger)]/30 bg-[color:var(--danger-soft)] p-4 text-sm leading-6 text-[color:var(--danger)]">
            <div className="flex gap-3">
              <Warning size={21} weight="fill" className="shrink-0" aria-hidden="true" />
              <p>JSON 可能包含 accessToken、sessionToken 或 refreshToken，等同登录凭证。不要把文件发给他人，也不要用于无权使用的账号。</p>
            </div>
          </div>

          <input
            ref={fileInputRef}
            type="file"
            accept=".json,application/json"
            multiple
            aria-label="选择要转换的 JSON 文件"
            className="sr-only"
            onChange={(event) => void convertFiles(event.target.files)}
          />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="button-secondary tactile mt-5 min-h-12 w-full"
          >
            <UploadSimple size={19} aria-hidden="true" />
            选择 JSON 文件（支持多选）
          </button>
          <p className="mt-2 text-xs leading-5 text-black/45">
            单次最多 {COCKPIT_LIMITS.maxFilesPerBatch} 个文件，累计不超过 {COCKPIT_LIMITS.maxTotalFileBytes / (1024 * 1024)} MB。
          </p>

          {selectedFiles.length ? (
            <div className="mt-4 rounded-[12px] border hairline bg-black/[.035] p-4 text-sm leading-6">
              <p className="font-semibold">已解析 {selectedFiles.length} 个文件</p>
              <ul className="mt-2 space-y-1 text-black/60">
                {selectedFiles.map((name) => <li key={name}>{name}</li>)}
              </ul>
            </div>
          ) : null}

          <div className="my-5 flex items-center gap-3 text-xs text-black/40" aria-hidden="true">
            <span className="h-px flex-1 bg-[color:var(--line)]" />
            或粘贴 JSON
            <span className="h-px flex-1 bg-[color:var(--line)]" />
          </div>

          <label htmlFor="converter-input" className="text-sm font-semibold">JSON 内容</label>
          <textarea
            id="converter-input"
            value={inputText}
            onChange={(event) => setInputText(event.target.value)}
            spellCheck={false}
            autoComplete="off"
            placeholder={'{"user":{"email":"name@example.com"},"account":{"id":"..."},"accessToken":"..."}'}
            className="field mono mt-2 min-h-72 resize-y p-4 text-xs leading-6"
          />
          <button
            type="button"
            onClick={convertPastedJson}
            className="button-primary tactile mt-4 min-h-12 w-full"
          >
            <FileJs size={19} aria-hidden="true" />
            转换为 Cockpit JSON
          </button>
        </section>

        <section className="rounded-[14px] border border-[color:var(--line-strong)] bg-[color:var(--panel)] p-5 sm:p-6" aria-labelledby="converter-output-title">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="mono text-xs text-black/45">02 / 输出</p>
              <h2 id="converter-output-title" className="mt-2 text-2xl font-semibold tracking-[-.035em]">Cockpit 导入 JSON</h2>
            </div>
            <button
              type="button"
              onClick={downloadOutput}
              disabled={!outputText}
              className="button-secondary disabled:cursor-not-allowed disabled:opacity-40"
            >
              <DownloadSimple size={17} aria-hidden="true" />
              下载 JSON
            </button>
          </div>

          <div className="mt-5 grid grid-cols-2 gap-3">
            <div className="rounded-[12px] border hairline p-4">
              <p className="mono text-2xl font-semibold">{result.accounts.length}</p>
                <p className="mt-1 text-xs text-black/45">已转换账号</p>
            </div>
            <div className="rounded-[12px] border hairline p-4">
              <p className="mono text-2xl font-semibold">{result.issues.length}</p>
              <p className="mt-1 text-xs text-black/45">跳过项目</p>
            </div>
          </div>

          {fileSummary ? (
            <p className="mt-3 text-xs leading-5 text-black/50">{fileSummary}</p>
          ) : null}

          {result.accounts.length ? (
            <div className="mt-4 overflow-hidden rounded-[12px] border hairline">
              {result.accounts.map((item, index) => (
                <div key={`${item.sourceName}-${item.sourcePath}`} className="flex items-center justify-between gap-4 border-b hairline p-3 text-sm last:border-b-0">
                  <div className="min-w-0">
                    <p className="truncate font-semibold">{maskEmail(item.email)}</p>
                    <p className="mt-1 truncate text-xs text-black/45">{item.sourceName} · {item.sourcePath}</p>
                  </div>
                  <span className="mono shrink-0 text-xs text-black/40">#{String(index + 1).padStart(2, "0")}</span>
                </div>
              ))}
            </div>
          ) : null}

          {result.issues.length ? (
            <div className="mt-4 rounded-[12px] border border-[color:var(--danger)]/30 bg-[color:var(--danger-soft)] p-4 text-sm leading-6 text-[color:var(--danger)]">
              {result.issues.map((issue) => <p key={`${issue.sourceName}-${issue.path}-${issue.reason}`}>{issue.sourceName} {issue.path}：{issue.reason}</p>)}
            </div>
          ) : null}

          {error ? <p role="alert" className="mt-4 text-sm font-semibold text-[color:var(--danger)]">{error}</p> : null}

          <label htmlFor="converter-output" className="mt-5 block text-sm font-semibold">转换结果</label>
          <textarea
            id="converter-output"
            value={outputText}
            readOnly
            spellCheck={false}
            placeholder="转换完成后会在这里显示 Cockpit JSON。"
            className="field mono mt-2 min-h-72 resize-y p-4 text-xs leading-6"
          />

          {outputText ? (
            <div className="mt-4 rounded-[12px] border border-[color:var(--success)]/25 bg-[color:var(--success-soft)] p-4 text-sm leading-6 text-[color:var(--success)]">
              <div className="flex gap-3">
                <CheckCircle size={21} weight="fill" className="shrink-0" aria-hidden="true" />
                <p>
                  转换完成：{result.accounts.length} 个账号已通过必要字段校验（accessToken、account_id、email、id_token）。下载后回到 Cockpit Tools，进入 Codex → “+” → “导入”，选择刚生成的文件。
                </p>
              </div>
              {result.issues.length ? (
                <p className="mt-2 text-xs opacity-80">
                  另有 {result.issues.length} 个项目因缺少关键字段或解析失败被跳过，未写入输出。
                </p>
              ) : null}
              <p className="mt-2 text-xs opacity-80">
                字段校验不等于账号当前可用；过期、封禁等状态仍需导入 Cockpit 后确认。
              </p>
            </div>
          ) : null}
        </section>
      </div>

      <footer className="mt-8 max-w-[88ch] border-t border-[color:var(--line-strong)] pt-6 text-sm leading-6 text-black/55">
        <p>格式兼容逻辑参考 MIT 许可的开源项目：</p>
        <a
          href="https://github.com/gtxx3600/GPTSession2CPAandSub2API"
          target="_blank"
          rel="noreferrer"
          className="mt-2 inline-flex min-h-11 items-center gap-2 font-semibold text-[color:var(--ink)] hover:underline"
        >
          gtxx3600/GPTSession2CPAandSub2API
          <ArrowSquareOut size={16} aria-hidden="true" />
        </a>
      </footer>
    </main>
  );
}
