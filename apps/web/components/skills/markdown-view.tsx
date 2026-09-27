"use client";

import React, { useState } from "react";
import { Check, Copy, Sparkle, TerminalWindow, Code as CodeIcon, WarningCircle, Lightbulb, Info } from "@phosphor-icons/react";

function safeLinkHref(value: string): string | null {
  const href = value.trim();
  if (!href) return null;
  if (href.startsWith("/") && !href.startsWith("//")) return href;
  try {
    const parsed = new URL(href);
    return parsed.protocol === "https:" || parsed.protocol === "http:" ? href : null;
  } catch {
    return null;
  }
}

function getLanguageMeta(rawLang: string) {
  const lang = (rawLang || "").trim().toLowerCase();
  if (!lang || lang === "text" || lang === "prompt" || lang === "txt" || lang === "指令") {
    return {
      label: "提示词 / 指令",
      icon: <Sparkle size={14} className="text-amber-400" />,
      tagColor: "text-amber-300 bg-amber-400/10 border-amber-400/20",
    };
  }
  if (lang === "bash" || lang === "sh" || lang === "shell" || lang === "cmd" || lang === "terminal") {
    return {
      label: "终端命令",
      icon: <TerminalWindow size={14} className="text-emerald-400" />,
      tagColor: "text-emerald-300 bg-emerald-400/10 border-emerald-400/20",
    };
  }
  if (lang === "json") {
    return {
      label: "JSON",
      icon: <CodeIcon size={14} className="text-sky-400" />,
      tagColor: "text-sky-300 bg-sky-400/10 border-sky-400/20",
    };
  }
  if (lang === "python" || lang === "py") {
    return {
      label: "Python",
      icon: <CodeIcon size={14} className="text-blue-400" />,
      tagColor: "text-blue-300 bg-blue-400/10 border-blue-400/20",
    };
  }
  if (lang === "code" || lang === "text") {
    return {
      label: "文本 / 指令",
      icon: <CodeIcon size={14} className="text-neutral-300" />,
      tagColor: "text-neutral-300 bg-neutral-400/10 border-neutral-400/20",
    };
  }
  return {
    label: rawLang.toUpperCase(),
    icon: <CodeIcon size={14} className="text-[color:var(--brand)]" />,
    tagColor: "text-neutral-300 bg-neutral-400/10 border-neutral-400/20",
  };
}

function CodeBlock({ code, language }: { code: string; language: string }) {
  const [copied, setCopied] = useState(false);
  const [copyFailed, setCopyFailed] = useState(false);
  const meta = getLanguageMeta(language);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopyFailed(false);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
      setCopyFailed(true);
      setTimeout(() => setCopied(false), 3000);
    }
  };

  return (
    <div className="relative my-4 overflow-hidden rounded-xl border border-[color:var(--line-strong)] bg-[#171914] text-[#f4f1e8] font-mono text-xs sm:text-sm shadow-sm transition">
      <div className="flex items-center justify-between border-b border-white/10 bg-black/40 px-3.5 py-2 text-xs">
        <div className={`inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 border font-sans font-medium ${meta.tagColor}`}>
          {meta.icon}
          <span>{meta.label}</span>
        </div>
        <button
          type="button"
          onClick={handleCopy}
          className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-sans font-medium transition ${
            copied
              ? "bg-emerald-500/20 text-emerald-300"
              : copyFailed
              ? "bg-rose-500/20 text-rose-300"
              : "bg-white/10 text-neutral-200 hover:bg-white/20 hover:text-white"
          }`}
        >
          {copied ? <Check size={13} className="text-emerald-400" /> : <Copy size={13} />}
          <span>{copied ? "已复制" : copyFailed ? "复制失败" : "一键复制"}</span>
        </button>
      </div>
      <pre className="overflow-x-auto p-4 leading-relaxed font-mono select-all">
        <code>{code}</code>
      </pre>
    </div>
  );
}

function CalloutBlock({ lines, formatInline }: { lines: string[]; formatInline: (text: string) => React.ReactNode }) {
  const fullText = lines.join("\n").trim();
  let type: "info" | "tip" | "warning" = "info";
  let content = fullText;

  if (/^\[!TIP\]/i.test(fullText) || fullText.includes("💡") || fullText.includes("福利") || fullText.includes("推荐")) {
    type = "tip";
    content = content.replace(/^\[!TIP\]\s*/i, "");
  } else if (/^\[!WARNING\]|^\[!CAUTION\]/i.test(fullText) || fullText.includes("⚠️") || fullText.includes("避坑") || fullText.includes("切勿")) {
    type = "warning";
    content = content.replace(/^\[!(WARNING|CAUTION)\]\s*/i, "");
  } else if (/^\[!NOTE\]|^\[!IMPORTANT\]/i.test(fullText)) {
    type = "info";
    content = content.replace(/^\[!(NOTE|IMPORTANT)\]\s*/i, "");
  }

  const styles = {
    info: {
      border: "border-l-4 border-[color:var(--brand-strong)] bg-[color:var(--brand-soft)]/30 text-[color:var(--foreground)]",
      icon: <Info size={16} className="text-[color:var(--brand-strong)] mt-0.5 shrink-0" />,
    },
    tip: {
      border: "border-l-4 border-emerald-600 bg-emerald-500/10 text-emerald-950 dark:text-emerald-100",
      icon: <Lightbulb size={16} className="text-emerald-600 mt-0.5 shrink-0" />,
    },
    warning: {
      border: "border-l-4 border-amber-600 bg-amber-500/10 text-amber-950 dark:text-amber-100",
      icon: <WarningCircle size={16} className="text-amber-600 mt-0.5 shrink-0" />,
    },
  }[type];

  return (
    <div className={`my-4 flex items-start gap-3 rounded-r-xl px-4 py-3 text-xs sm:text-sm leading-relaxed ${styles.border}`}>
      {styles.icon}
      <div className="flex-1 space-y-1">
        {content.split("\n").map((line, idx) => (
          <div key={idx}>{formatInline(line)}</div>
        ))}
      </div>
    </div>
  );
}

export function MarkdownView({ content = "" }: { content: string }) {
  if (!content) return null;

  const lines = content.split("\n");
  const nodes: React.ReactNode[] = [];

  let inCodeBlock = false;
  let codeBuffer: string[] = [];
  let codeLang = "";

  let inTable = false;
  let tableRows: string[][] = [];

  let inOrderedList = false;
  let orderedItems: { num: number; node: React.ReactNode }[] = [];
  let orderedStart = 1;

  let inUnorderedList = false;
  let unorderedItems: React.ReactNode[] = [];

  let inBlockquote = false;
  let blockquoteLines: string[] = [];

  const flushTable = (key: string) => {
    if (tableRows.length === 0) return;
    const [header, , ...body] = tableRows;
    nodes.push(
      <div key={key} className="my-5 overflow-x-auto">
        <table className="w-full border-collapse text-left text-xs sm:text-sm">
          {header ? (
            <thead>
              <tr className="border-b border-[color:var(--line-strong)] bg-[color:var(--hover)] font-semibold text-[color:var(--foreground)]">
                {header.map((col, idx) => (
                  <th key={idx} className="px-3.5 py-2.5">
                    {col.trim()}
                  </th>
                ))}
              </tr>
            </thead>
          ) : null}
          <tbody>
            {body.map((row, rIdx) => (
              <tr key={rIdx} className="border-b border-[color:var(--line)] hover:bg-[color:var(--hover)]/50">
                {row.map((cell, cIdx) => (
                  <td key={cIdx} className="px-3.5 py-2.5 text-[color:var(--muted)]">
                    {formatInline(cell.trim())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
    tableRows = [];
    inTable = false;
  };

  const flushOrderedList = (key: string) => {
    if (orderedItems.length === 0) return;
    nodes.push(
      <ol
        key={key}
        start={orderedStart}
        className="my-3 ml-6 list-decimal space-y-1.5 text-xs sm:text-sm text-[color:var(--muted)] leading-relaxed"
      >
        {orderedItems.map((item, idx) => (
          <li key={idx} value={item.num}>
            {item.node}
          </li>
        ))}
      </ol>
    );
    orderedItems = [];
    inOrderedList = false;
  };

  const flushUnorderedList = (key: string) => {
    if (unorderedItems.length === 0) return;
    nodes.push(
      <ul
        key={key}
        className="my-3 ml-6 list-disc space-y-1.5 text-xs sm:text-sm text-[color:var(--muted)] leading-relaxed"
      >
        {unorderedItems.map((node, idx) => (
          <li key={idx}>{node}</li>
        ))}
      </ul>
    );
    unorderedItems = [];
    inUnorderedList = false;
  };

  const flushBlockquote = (key: string) => {
    if (blockquoteLines.length === 0) return;
    nodes.push(
      <CalloutBlock
        key={key}
        lines={blockquoteLines}
        formatInline={formatInline}
      />
    );
    blockquoteLines = [];
    inBlockquote = false;
  };

  const flushAll = (key: string) => {
    if (inTable) flushTable(`table-${key}`);
    if (inOrderedList) flushOrderedList(`ol-${key}`);
    if (inUnorderedList) flushUnorderedList(`ul-${key}`);
    if (inBlockquote) flushBlockquote(`quote-${key}`);
  };

  const formatInline = (text: string): React.ReactNode => {
    // Basic inline formatting: **bold**, `code`, [link](url)
    const parts = text.split(/(\*\*.*?\*\*|`.*?`|\[.*?\]\(.*?\))/g);
    return parts.map((part, i) => {
      if (part.startsWith("**") && part.endsWith("**")) {
        return <strong key={i} className="font-bold text-[color:var(--foreground)]">{part.slice(2, -2)}</strong>;
      }
      if (part.startsWith("`") && part.endsWith("`")) {
        return (
          <code key={i} className="rounded bg-[color:var(--hover)] px-1.5 py-0.5 font-mono text-xs text-[color:var(--brand-strong)]">
            {part.slice(1, -1)}
          </code>
        );
      }
      const linkMatch = part.match(/^\[(.*?)\]\((.*?)\)$/);
      if (linkMatch) {
        const href = safeLinkHref(linkMatch[2]);
        if (!href) {
          return <span key={i}>{linkMatch[1]}</span>;
        }
        const external = /^https?:\/\//i.test(href);
        return (
          <a
            key={i}
            href={href}
            target={external ? "_blank" : undefined}
            rel={external ? "noopener noreferrer" : undefined}
            className="text-[color:var(--brand-strong)] underline underline-offset-2 hover:opacity-80"
          >
            {linkMatch[1]}
          </a>
        );
      }
      return part;
    });
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Code block toggle (supports indented blocks like under list items)
    if (line.trim().startsWith("```")) {
      if (inCodeBlock) {
        // Strip common leading indent
        const minIndent = codeBuffer
          .filter((l) => l.trim().length > 0)
          .reduce((min, l) => {
            const match = l.match(/^(\s*)/);
            return Math.min(min, match ? match[1].length : 0);
          }, Infinity);
        const cleanedCode = (minIndent > 0 && minIndent !== Infinity
          ? codeBuffer.map((l) => (l.length >= minIndent ? l.slice(minIndent) : l))
          : codeBuffer
        ).join("\n");

        nodes.push(
          <CodeBlock
            key={`code-${i}`}
            code={cleanedCode}
            language={codeLang}
          />
        );
        codeBuffer = [];
        codeLang = "";
        inCodeBlock = false;
      } else {
        flushAll(`before-code-${i}`);
        inCodeBlock = true;
        codeLang = line.trim().slice(3).trim();
      }
      continue;
    }

    if (inCodeBlock) {
      codeBuffer.push(line);
      continue;
    }

    // Blockquote
    if (line.trim().startsWith(">")) {
      if (inTable) flushTable(`table-${i}`);
      if (inOrderedList) flushOrderedList(`ol-${i}`);
      if (inUnorderedList) flushUnorderedList(`ul-${i}`);
      inBlockquote = true;
      const quoteContent = line.trim().startsWith("> ")
        ? line.trim().slice(2)
        : line.trim().slice(1);
      blockquoteLines.push(quoteContent);
      continue;
    } else if (inBlockquote) {
      flushBlockquote(`quote-${i}`);
    }

    // Table row detection
    if (line.trim().startsWith("|") && line.trim().endsWith("|")) {
      if (inOrderedList) flushOrderedList(`ol-${i}`);
      if (inUnorderedList) flushUnorderedList(`ul-${i}`);
      inTable = true;
      const cells = line.trim().slice(1, -1).split("|");
      tableRows.push(cells);
      continue;
    } else if (inTable) {
      flushTable(`table-${i}`);
    }

    // Numbered list item
    const numMatch = line.trim().match(/^(\d+)\.\s+(.*)$/);
    if (numMatch) {
      if (inUnorderedList) flushUnorderedList(`ul-${i}`);
      const itemNum = parseInt(numMatch[1], 10);
      if (!inOrderedList) {
        inOrderedList = true;
        orderedStart = itemNum;
        orderedItems = [];
      }
      orderedItems.push({
        num: itemNum,
        node: formatInline(numMatch[2]),
      });
      continue;
    }

    // Bullet list item
    if (line.trim().startsWith("- ") || line.trim().startsWith("* ")) {
      if (inOrderedList) flushOrderedList(`ol-${i}`);
      if (!inUnorderedList) {
        inUnorderedList = true;
        unorderedItems = [];
      }
      unorderedItems.push(formatInline(line.trim().slice(2)));
      continue;
    }

    // Non-list line flushes list state
    if (inOrderedList) flushOrderedList(`ol-${i}`);
    if (inUnorderedList) flushUnorderedList(`ul-${i}`);

    // Horizontal rule
    if (line.trim() === "---" || line.trim() === "***") {
      nodes.push(<hr key={i} className="my-6 border-[color:var(--line)]" />);
      continue;
    }

    // Headings
    if (line.startsWith("# ")) {
      nodes.push(
        <h1 key={i} className="mt-8 mb-4 text-2xl font-bold tracking-tight text-[color:var(--foreground)] sm:text-3xl">
          {formatInline(line.slice(2))}
        </h1>
      );
      continue;
    }
    if (line.startsWith("## ")) {
      nodes.push(
        <h2 key={i} className="mt-6 mb-3 text-xl font-bold tracking-tight text-[color:var(--foreground)] sm:text-2xl">
          {formatInline(line.slice(3))}
        </h2>
      );
      continue;
    }
    if (line.startsWith("### ")) {
      nodes.push(
        <h3 key={i} className="mt-5 mb-2 text-lg font-bold text-[color:var(--foreground)] sm:text-xl">
          {formatInline(line.slice(4))}
        </h3>
      );
      continue;
    }
    if (line.startsWith("#### ")) {
      nodes.push(
        <h4 key={i} className="mt-4 mb-2 text-base font-bold text-[color:var(--foreground)]">
          {formatInline(line.slice(5))}
        </h4>
      );
      continue;
    }

    // Paragraph
    if (line.trim()) {
      nodes.push(
        <p key={i} className="my-3 text-xs sm:text-sm text-[color:var(--muted)] leading-relaxed">
          {formatInline(line)}
        </p>
      );
    }
  }

  flushAll("end");

  if (inCodeBlock) {
    nodes.push(<CodeBlock key="code-end" code={codeBuffer.join("\n")} language={codeLang} />);
  }

  return <div className="markdown-prose my-4">{nodes}</div>;
}
