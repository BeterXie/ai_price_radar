# Source connectors

AI Price Radar separates source reading from database publication. A connector converts one source into the common record shape; the existing import pipeline remains responsible for validation, idempotency, history, snapshots and PostgreSQL writes.

## Built-in connectors

- `ldxp`: reads the crawler SQLite database.
- `merchant-json`: reads a local JSON file or a public HTTPS JSON Feed.
- `dujiao-next`: reads a Dujiao-Next shop through its unauthenticated public REST API.

Production publication must use one authoritative multi-source transaction:

```bash
python pipeline/publish_catalog.py \
  --ldxp-db /data/ldxp_crawler.db \
  --dujiao-db /data/ldxp_crawler.db \
  --merchant-sources /data/merchant_sources.json
```

`publish_catalog.py` creates one draft snapshot, imports every configured source, and publishes only after all imports succeed. A failed source rolls the transaction back and leaves the previous complete snapshot online. `sync_source.py` remains a compatibility tool for local or incremental operations; it carries the current catalog forward and must not be used as the authoritative production refresh.

## Merchant JSON Feed

The response may be an array of items or an object containing `shop`, `updated_at` and `items`.

```json
{
  "shop": {"token": "merchant-demo", "name": "Demo source", "url": "https://merchant.example.com"},
  "updated_at": "2026-07-29T00:00:00Z",
  "items": [
    {
      "id": "chatgpt-plus-monthly",
      "name": "ChatGPT Plus 1 month",
      "category": "OpenAI",
      "price": 99,
      "currency": "CNY",
      "stock": 8,
      "url": "https://merchant.example.com/products/chatgpt-plus"
    }
  ]
}
```

Required per item: stable `id`, human-readable `name`, and public `url`. Price and stock may be omitted when unknown. The connector limits response size, accepts HTTPS for remote feeds, and normalizes records before import. Production deployments should additionally apply egress allow-lists or an outbound proxy.

`currency` defaults to `CNY`, is normalized to an ISO 4217 code, and is preserved on the offer and its history. `stock_count` is the canonical stock field; `stock` remains accepted for compatibility with the example above. Product-level minimum prices, price filters, trends and watch thresholds currently aggregate CNY offers only. Other currencies remain visible on individual offers and are never relabeled or exchange-rate converted.

Merchant JSON Feed submissions share the `source_intakes` review state machine, but the LDXP Worker bridge does not claim them. A feed remains non-onboarded until a separately reviewed consumer can prove a successful published sync.

## Dujiao-Next

Pass the public shop root URL, without a path, query string or credentials. The connector validates the public HTTPS origin, disables redirects, reads `/api/v1/public/config` and `/categories`, paginates `/products`, and fetches each product detail by slug. Multi-SKU products emit one record per active SKU so that monthly, quarterly and annual variants cannot overwrite each other. Conditional promotion and member prices remain in `raw_json`; the normalized `listed_price` uses the public base price until the common offer model can express price conditions.

The connector caps response size, pages and product count. Run it behind an outbound allow-list or proxy in production because application-level DNS validation cannot fully eliminate DNS rebinding.

### Public candidate discovery

The crawler CLI provides a separate `discover-dujiao` flow for seed pages and low-frequency Bing RSS results. It reduces `/buy/...` and `/products/...` hits to a validated HTTPS origin, excludes official Dujiao-Next domains, checks the homepage fingerprint and public product API, and only queues stores whose real product data matches the AI catalog vocabulary.

Discovery evidence is stored privately in the crawler SQLite `dujiao_candidates` table. Human `approve` or `reject` decisions never publish by themselves. The production publisher reads only candidates that are approved, API-verified, and still in a publishable verification state; an arbitrary Dujiao URL cannot enter the public snapshot. The development-only bypass requires both `--allow-unreviewed-source` and `AI_PRICE_RADAR_ALLOW_UNREVIEWED_DUJIAO=1`.

The Common Crawl CDX service indexes URLs rather than page body text. Arbitrary-domain discovery from template prose requires a separate URL Index/WARC content-analysis job; the low-frequency discovery command deliberately does not issue broad or misleading CDX queries.

## Adding a connector

Implement the connector protocol in `pipeline/connectors/base.py`, return common records, add fixtures and tests, then register it in `pipeline/connectors/__init__.py`. A connector must not bypass moderation, write directly to public tables, store credentials, or hide source URLs.
