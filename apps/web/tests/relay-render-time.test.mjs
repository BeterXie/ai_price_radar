import assert from "node:assert/strict";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { RelayStationCard } from "../components/relay-station-card.tsx";

test("relay first render uses the server time across client clock changes", () => {
  const timestamp = "2026-10-26T01:00:00Z";
  const initialNow = Date.parse(timestamp) + 119999;
  const station = {
    id: 1, name: "Relay", url: "https://relay.example.com", updated_at: timestamp,
    supported_models: [], tags: [], groups: [],
    model_catalog: {
      status: "ok", synced_at: timestamp, checked_at: timestamp, models: [],
      group_catalog: { status: "ok", synced_at: timestamp, source: "key_billing", groups: [{ id: "g", name: "VIP", ratio: 0.5, models: null }] },
    },
    health: { checked_at: timestamp, recent_samples: [] },
  };
  const realNow = Date.now;
  try {
    Date.now = () => initialNow;
    const server = renderToStaticMarkup(createElement(RelayStationCard, { station, initialNow }));
    Date.now = () => initialNow + 86400000;
    const client = renderToStaticMarkup(createElement(RelayStationCard, { station, initialNow }));
    assert.equal(client, server);
    assert.match(client, /1 分钟前/);
    assert.doesNotMatch(client, /1 天前/);
  } finally {
    Date.now = realNow;
  }
});
