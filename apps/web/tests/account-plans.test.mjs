import assert from "node:assert/strict";
import test from "node:test";
import { BRAND_TABS, PRODUCT_CATEGORIES, PRODUCT_TABS } from "../lib/catalog.ts";

test("official plan filters exclude merchant labels and uncertain tiers", () => {
  assert.deepEqual(PRODUCT_TABS.OpenAI.filter((tab) => !tab.other).map((tab) => tab.label), [
    "Free", "Plus", "Go", "Pro 100 / 5x", "Pro 200 / 20x", "Pro 500", "Business / Team", "Edu", "Enterprise",
  ]);
  assert.deepEqual(PRODUCT_TABS.Claude.filter((tab) => !tab.other).map((tab) => tab.label), [
    "Pro", "Max 5x", "Max 20x", "Team", "Enterprise",
  ]);
});

test("MUSE and JEV have separate filters without invented official plans", () => {
  for (const brand of ["MUSE", "JEV"]) {
    assert.ok(BRAND_TABS.includes(brand));
    const tabs = PRODUCT_TABS[brand];
    assert.ok(tabs.every((tab) => tab.other));
    assert.ok(tabs.some((tab) => tab.slug === `${brand.toLowerCase()}-account`));
    assert.ok(tabs.some((tab) => tab.slug === `${brand.toLowerCase()}-invite`));
    assert.ok(tabs.some((tab) => tab.slug === `${brand.toLowerCase()}-api-credit`));
  }
});

test("auxiliary catalog families expose stable product filters", () => {
  const families = {
    "邮箱": ["email-gmail", "email-outlook", "email-education", "email-icloud", "email-account"],
    "接码 / 验证": ["chatgpt-access-service", "verification-google", "verification-claude", "verification-cursor", "muse-access-service", "jev-access-service", "verification-social", "verification-paypal", "verification-general", "verification-kyc"],
    "虚拟卡": ["virtual-card"],
    "礼品卡": ["gift-card"],
    "社媒账号": ["social-media-account"],
    "Apple ID": ["apple-id-account"],
    VPS: ["vps"],
  };
  for (const [family, slugs] of Object.entries(families)) {
    assert.ok(PRODUCT_CATEGORIES.includes(family));
    assert.deepEqual(PRODUCT_TABS[family].map((tab) => tab.slug), slugs);
    assert.ok(PRODUCT_TABS[family].every((tab) => tab.other));
  }
});
