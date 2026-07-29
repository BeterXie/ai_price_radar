# Source connectors

AI Price Radar separates source reading from database publication. A connector converts one source into the common record shape; the existing import pipeline remains responsible for validation, idempotency, history, snapshots and PostgreSQL writes.

## Built-in connectors

- `ldxp`: reads the crawler SQLite database.
- `merchant-json`: reads a local JSON file or a public HTTPS JSON Feed.

```bash
python pipeline/sync_source.py --connector ldxp --source /data/ldxp_crawler.db
python pipeline/sync_source.py --connector merchant-json --source https://merchant.example.com/feed.json
```

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

## Adding a connector

Implement the connector protocol in `pipeline/connectors/base.py`, return common records, add fixtures and tests, then register it in `pipeline/connectors/__init__.py`. A connector must not bypass moderation, write directly to public tables, store credentials, or hide source URLs.
