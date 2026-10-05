import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { MarkdownView } from "../components/skills/markdown-view.tsx";

function render(content) {
  return renderToStaticMarkup(React.createElement(MarkdownView, { content }));
}

test("Markdown images retain complete balanced and escaped URL parentheses", () => {
  for (const [source, expected] of [
    ["https://example.com/preview(1).png", "https://example.com/preview(1).png"],
    ["https://example.com/preview(a(b)c).png", "https://example.com/preview(a(b)c).png"],
    [String.raw`https://example.com/preview\(1\).png`, "https://example.com/preview(1).png"],
  ]) {
    const html = render(`![截图](${source})`);
    assert.ok(html.includes(`src="${expected}"`), html);
    assert.ok(html.includes('alt="截图"'), html);
  }
});

test("Markdown image titles are separate from the requested URL", () => {
  for (const title of ['"预览"', "'预览'", "(预览)"]) {
    const html = render(`![截图](https://example.com/preview(1).png ${title})`);
    assert.ok(html.includes('src="https://example.com/preview(1).png"'), html);
    assert.ok(html.includes('title="预览"'), html);
  }
});

test("ordinary and rooted Markdown images keep safe loading attributes", () => {
  for (const source of ["https://example.com/preview.png", "/demos/preview.png"]) {
    const html = render(`![截图](${source})`);
    assert.ok(html.includes(`src="${source}"`), html);
    assert.ok(html.includes('loading="lazy"'), html);
    assert.ok(html.includes('referrerPolicy="no-referrer"'), html);
  }
});

test("Markdown images work inside existing bold and link formatting", () => {
  const html = render("**![截图](https://example.com/preview.png)** [![示例](/demos/preview.png)](https://example.com/detail)");
  assert.match(html, /<strong[^>]*><img src="https:\/\/example\.com\/preview\.png"/);
  assert.match(html, /<a[^>]*href="https:\/\/example\.com\/detail"[^>]*><img src="\/demos\/preview\.png"/);
});

test("existing text formatting and code examples still render correctly", () => {
  const html = render("**加粗** `指令` [链接](https://example.com/detail)");
  assert.match(html, /<strong[^>]*>加粗<\/strong>/);
  assert.match(html, /<code[^>]*>指令<\/code>/);
  assert.match(html, /<a[^>]*href="https:\/\/example\.com\/detail"[^>]*>链接<\/a>/);
  for (const content of [
    "`![截图](https://example.com/preview.png)`",
    "```markdown\n![截图](https://example.com/preview.png)\n```",
    String.raw`\![截图](https://example.com/preview.png)`,
  ]) {
    assert.doesNotMatch(render(content), /<img\b/);
  }
});

test("unsafe image and link destinations cannot create active elements", () => {
  for (const destination of ["javascript:alert(1)", "data:image/svg+xml;base64,PHN2Zz4=", "//example.com/preview.png"]) {
    const html = render(`![截图](${destination}) [链接](${destination})`);
    assert.doesNotMatch(html, /<(?:img|a)\b/);
    assert.match(html, /截图/);
    assert.match(html, /链接/);
  }
});

test("raw HTML in Markdown remains escaped text", () => {
  const html = render('<img src="https://example.com/preview.png" onerror="alert(1)">');
  assert.doesNotMatch(html, /<img\b/);
  assert.match(html, /&lt;img/);
});
