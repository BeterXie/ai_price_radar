import assert from "node:assert/strict";
import test from "node:test";

import {
  DISMISS_KEY_PREFIX,
  noticeVersionKey,
  pruneStaleDismissKeys,
} from "../components/site-notice.tsx";

function withFakeLocalStorage(store, run) {
  const original = globalThis.localStorage;
  globalThis.localStorage = {
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
    if (original === undefined) delete globalThis.localStorage;
    else globalThis.localStorage = original;
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

test("prune removes stale dismissal keys but keeps the current one", () => {
  const currentKey = `${DISMISS_KEY_PREFIX}${noticeVersionKey(NOTICE)}`;
  const store = new Map([
    [`${DISMISS_KEY_PREFIX}old-version-1`, "1"],
    [`${DISMISS_KEY_PREFIX}old-version-2`, "1"],
    [currentKey, "1"],
    ["apr:community:session-count", "3"],
    ["unrelated", "value"],
  ]);

  withFakeLocalStorage(store, () => pruneStaleDismissKeys(currentKey));

  assert.equal(store.has(currentKey), true);
  assert.equal(store.has(`${DISMISS_KEY_PREFIX}old-version-1`), false);
  assert.equal(store.has(`${DISMISS_KEY_PREFIX}old-version-2`), false);
  // Unrelated storage keys are untouched.
  assert.equal(store.get("apr:community:session-count"), "3");
  assert.equal(store.get("unrelated"), "value");
});

test("prune tolerates a missing localStorage", () => {
  const original = globalThis.localStorage;
  delete globalThis.localStorage;
  try {
    assert.doesNotThrow(() => pruneStaleDismissKeys("apr:notice:dismissed:x"));
  } finally {
    if (original !== undefined) globalThis.localStorage = original;
  }
});
