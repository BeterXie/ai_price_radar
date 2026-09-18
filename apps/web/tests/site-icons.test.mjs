import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";


const __dirname = path.dirname(fileURLToPath(import.meta.url));
const webRoot = path.resolve(__dirname, "..");

test("site icons: all required favicon and icon assets exist on disk", () => {
  const requiredFiles = [
    "app/favicon.ico",
    "public/favicon.ico",
    "app/icon.png",
    "public/icon.png",
    "app/icon.svg",
    "public/icon.svg",
    "app/apple-icon.png",
    "public/apple-icon.png",
    "public/brand/logo-icon.png",
  ];

  for (const relPath of requiredFiles) {
    const fullPath = path.join(webRoot, relPath);
    assert.ok(fs.existsSync(fullPath), `File must exist: ${relPath}`);
    const stats = fs.statSync(fullPath);
    assert.ok(stats.size > 0, `File must not be empty: ${relPath}`);
  }
});

test("site icons: layout.tsx defines comprehensive icons metadata for browser tabs", () => {
  const layoutPath = path.join(webRoot, "app/layout.tsx");
  const content = fs.readFileSync(layoutPath, "utf-8");

  assert.match(content, /icons:\s*\{/, "layout.tsx must contain icons metadata");
  assert.match(content, /url:\s*["']\/favicon\.ico["']/, "must include /favicon.ico");
  assert.match(content, /url:\s*["']\/icon\.svg["']/, "must include /icon.svg");
  assert.match(content, /url:\s*["']\/icon\.png["']/, "must include /icon.png");
  assert.match(content, /url:\s*["']\/apple-icon\.png["']/, "must include /apple-icon.png");
  assert.match(content, /shortcut:\s*["']\/favicon\.ico["']/, "shortcut must be /favicon.ico");
});

test("site icons: header logo uses unoptimized to avoid proxy attachment headers", () => {
  const headerPath = path.join(webRoot, "components/site-header.tsx");
  const content = fs.readFileSync(headerPath, "utf-8");

  assert.match(
    content,
    /<Image[\s\S]*?src="\/brand\/logo-icon\.png"[\s\S]*?unoptimized[\s\S]*?\/>/,
    "Header brand logo <Image> must have unoptimized attribute",
  );
});
