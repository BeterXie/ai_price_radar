import assert from "node:assert/strict";
import test from "node:test";

import {
  DISMISS_KEY_PREFIX,
  noticeVersionKey,
  pruneStaleDismissKeys,
} from "../components/site-notice.tsx";
import { safeNoticeLink } from "../lib/safe-url.ts";

function withFakeSessionStorage(store, run) {
  const original = globalThis.sessionStorage;
  globalThis.sessionStorage = {
    getItem: (key) => store.get(key) ?? null,
    setItem: (key, value) => store.set(key, String(value)),
    removeItem: (key) => store.delete(key),
    get length() {
      return store.size;
    },
    key: (index) => Array.from(store.keys())[index] ?? null,
  };
  try {
    return run();
  } finally {
    if (original === undefined) delete globalThis.sessionStorage;
    else globalThis.sessionStorage = original;
  }
}

const NOTICE = {
  enabled: true,
  badge: "最新动态",
  title: "标题 A",
  content: "正文 A",
  link_text: "查看",
  link_url: "/developers",
};

test("notice version key is stable and content-sensitive", () => {
  const key = noticeVersionKey(NOTICE);
  assert.equal(key, noticeVersionKey({ ...NOTICE }));
  // Any content change (even with the same title) produces a new version key,
  // so users who dismissed the old notice see the updated one again.
  assert.notEqual(key, noticeVersionKey({ ...NOTICE, content: "正文 B" }));
  assert.notEqual(key, noticeVersionKey({ ...NOTICE, link_url: "/skills" }));
  // Missing optional fields must not crash the hash.
  assert.equal(typeof noticeVersionKey({ enabled: true, title: "x" }), "string");
});

test("safeNoticeLink supports internal routes and external HTTPS URLs", () => {
  // Internal relative paths
  assert.deepEqual(safeNoticeLink("/developers"), { href: "/developers", isExternal: false });
  assert.deepEqual(safeNoticeLink("/skills?tab=all#top"), { href: "/skills?tab=all#top", isExternal: false });

  // External HTTPS URLs (e.g. QQ group link)
  assert.deepEqual(safeNoticeLink("https://qm.qq.com/q/zAbYAfRPji"), {
    href: "https://qm.qq.com/q/zAbYAfRPji",
    isExternal: true,
  });
  assert.deepEqual(safeNoticeLink("https://example.com/path"), {
    href: "https://example.com/path",
    isExternal: true,
  });

  // Invalid or insecure URLs
  assert.equal(safeNoticeLink("javascript:alert(1)"), null);
  assert.equal(safeNoticeLink("http://insecure.example.com"), null);
  assert.equal(safeNoticeLink("https://user:pass@example.com"), null);
  assert.equal(safeNoticeLink("//protocol-relative.example.com"), null);
  assert.equal(safeNoticeLink(""), null);
  assert.equal(safeNoticeLink(null), null);
});

test("prune removes stale dismissal keys in sessionStorage but keeps the current one", () => {
  const currentKey = `${DISMISS_KEY_PREFIX}${noticeVersionKey(NOTICE)}`;
  const store = new Map([
    [`${DISMISS_KEY_PREFIX}old-version-1`, "1"],
    [`${DISMISS_KEY_PREFIX}old-version-2`, "1"],
    [currentKey, "1"],
    ["apr:community:session-count", "3"],
    ["unrelated", "value"],
  ]);

  withFakeSessionStorage(store, () => pruneStaleDismissKeys(currentKey));

  assert.equal(store.has(currentKey), true);
  assert.equal(store.has(`${DISMISS_KEY_PREFIX}old-version-1`), false);
  assert.equal(store.has(`${DISMISS_KEY_PREFIX}old-version-2`), false);
  // Unrelated storage keys are untouched.
  assert.equal(store.get("apr:community:session-count"), "3");
  assert.equal(store.get("unrelated"), "value");
});

test("prune tolerates a missing sessionStorage", () => {
  const original = globalThis.sessionStorage;
  delete globalThis.sessionStorage;
  try {
    assert.doesNotThrow(() => pruneStaleDismissKeys("apr:notice:dismissed:x"));
  } finally {
    if (original !== undefined) globalThis.sessionStorage = original;
  }
});

