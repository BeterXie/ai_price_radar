"use client";

import React, { useState } from "react";
import { Check, Copy } from "@phosphor-icons/react";

function CodeBlock({ code, language }: { code: string; language: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = () => {
    navigator.clipboard.writeText(code).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <div className="relative my-4 overflow-hidden rounded-xl border border-[color:var(--line-strong)] bg-neutral-900 text-neutral-100 font-mono text-xs sm:text-sm">
      <div className="flex items-center justify-between border-b border-neutral-800 bg-neutral-950/60 px-4 py-2 text-neutral-400 text-xs">
        <span>{language || "code"}</span>
        <button
          type="button"
          onClick={handleCopy}
          className="inline-flex items-center gap-1 rounded px-2 py-0.5 hover:bg-neutral-800 hover:text-white transition"
        >
          {copied ? <Check size={13} className="text-emerald-400" /> : <Copy size={13} />}
          <span>{copied ? "已复制" : "复制"}</span>
        </button>
      </div>
      <pre className="overflow-x-auto p-4 leading-relaxed">
        <code>{code}</code>
      </pre>
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
        return (
          <a key={i} href={linkMatch[2]} target="_blank" rel="noreferrer" className="text-[color:var(--brand-strong)] underline underline-offset-2 hover:opacity-80">
            {linkMatch[1]}
          </a>
        );
      }
      return part;
    });
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Code block toggle
    if (line.startsWith("```")) {
      if (inCodeBlock) {
        nodes.push(
          <CodeBlock
            key={`code-${i}`}
            code={codeBuffer.join("\n")}
            language={codeLang}
          />
        );
        codeBuffer = [];
        codeLang = "";
        inCodeBlock = false;
      } else {
        if (inTable) flushTable(`table-${i}`);
        inCodeBlock = true;
        codeLang = line.slice(3).trim();
      }
      continue;
    }

    if (inCodeBlock) {
      codeBuffer.push(line);
      continue;
    }

    // Table row detection
    if (line.trim().startsWith("|") && line.trim().endsWith("|")) {
      inTable = true;
      const cells = line.trim().slice(1, -1).split("|");
      tableRows.push(cells);
      continue;
    } else if (inTable) {
      flushTable(`table-${i}`);
    }

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

    // Blockquote
    if (line.startsWith("> ")) {
      nodes.push(
        <blockquote key={i} className="my-3 border-l-4 border-[color:var(--brand)] bg-[color:var(--brand-soft)]/30 px-4 py-2 text-xs sm:text-sm text-[color:var(--foreground)] italic">
          {formatInline(line.slice(2))}
        </blockquote>
      );
      continue;
    }

    // Bullet list
    if (line.trim().startsWith("- ") || line.trim().startsWith("* ")) {
      nodes.push(
        <li key={i} className="ml-5 list-disc text-xs sm:text-sm text-[color:var(--muted)] leading-relaxed py-0.5">
          {formatInline(line.trim().slice(2))}
        </li>
      );
      continue;
    }

    // Numbered list
    const numMatch = line.trim().match(/^(\d+)\.\s+(.*)$/);
    if (numMatch) {
      nodes.push(
        <li key={i} className="ml-5 list-decimal text-xs sm:text-sm text-[color:var(--muted)] leading-relaxed py-0.5">
          {formatInline(numMatch[2])}
        </li>
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

  if (inTable) {
    flushTable("table-end");
  }

  return <div className="markdown-prose my-4">{nodes}</div>;
}
