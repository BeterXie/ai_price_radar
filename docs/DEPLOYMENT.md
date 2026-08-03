# Deployment

`ai.pricememo.cn` 的日常生产更新必须遵循 [生产快速部署](QUICK_DEPLOY.md)。本文件保留首次建站、网络、迁移和备份恢复说明。

## Single server

Recommended minimum:

- 2 CPU
- 4 GB RAM
- 30 GB SSD
- Docker Compose
- Caddy or Nginx

## Reverse proxy

生产 Compose 内置 Caddy。将 `.env` 中的 `SITE_ADDRESS` 设置为公网 HTTPS 地址，例如 `https://radar.example.com`，并确保域名 A/AAAA 记录指向服务器、80/443 入站端口可用。路由为：

```text
/          → web:3000
/api/*     → api:8000
/docs      → api:8000/docs, optionally restricted
```

启动前和启动命令：

```bash
python scripts/production_preflight.py
docker compose --profile production up --build -d
```

默认 Compose 不发布 PostgreSQL、API 或 Web 的宿主机端口。仅本地开发时使用 `docker-compose.dev.yml`，且端口只绑定到 `127.0.0.1`：

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build -d
```

## Security checklist

- Replace `ADMIN_API_KEY` with at least 32 random bytes.
- Do not expose PostgreSQL port publicly.
- Restrict `/admin` with Cloudflare Access or HTTP authentication.
- Keep `SEED_DEMO_DATA=false` in production.
- Keep report submission rate limiting enabled; defaults to 5 requests per client per hour.
- Configure `TRUSTED_PROXY_CIDRS` for the private reverse-proxy network so forwarded client addresses are only trusted from that network.
- Back up PostgreSQL every day.
- Keep the crawler and public web process in separate containers/users.
- Do not mount browser profiles into the public web container.
- Set `INTAKE_WORKER_KEY` to a secret distinct from `ADMIN_API_KEY`; the crawler and importer use it only for internal intake callbacks.
- Set `DETECTOR_WORKER_KEY` to a third secret, distinct from both `ADMIN_API_KEY` and `INTAKE_WORKER_KEY`; only the API and `source-detector` receive it.
- Keep `source-detector` off the default database network. It must not receive `DATABASE_URL`, Redis credentials, Docker socket mounts, or internal service credentials; retain only its API control network and outbound probe network.
- Configure real `SHOP_INTAKE_ADMIN_EMAILS`, `RESEND_API_KEY` and a verified `RESEND_FROM` before production deployment. SMTP remains available as a local/fallback provider. The API can start without either provider and retain messages in `notification_outbox`, but production preflight rejects incomplete mail configuration.

## Backup and restore rehearsal

Create and validate an atomic gzip backup:

```bash
bash scripts/backup_postgres.sh
```

Restore into an isolated test database (the default target ends in `_restore_test`) and verify that public tables exist:

```bash
bash scripts/restore_postgres.sh backups/price_radar_YYYYMMDD_HHMMSS.sql.gz
```

The restore script refuses a non-test database unless `ALLOW_RESTORE_OVERWRITE=1` is explicitly set. Do not use that override for routine rehearsals.

## pricememo.cn server integration

The existing `pricememo` Caddy container owns ports 80/443. Build the frontend locally with `NEXT_PUBLIC_API_BASE_URL=https://ai.pricememo.cn`; the server overlay uses that standalone artifact to avoid depending on Docker Hub during the server build. Deploy without the bundled proxy and attach API/Web to the existing external frontend network:

```bash
cd apps/web
NEXT_PUBLIC_API_BASE_URL=https://ai.pricememo.cn npm run build
cd ../..
```

```bash
docker compose -f docker-compose.yml -f docker-compose.pricememo.yml up --build -d
```

Append `deploy/ai.pricememo.cn.Caddyfile` to the existing Caddy configuration, validate it with `caddy validate`, then apply it with `caddy reload`. Set all public URLs in `.env` to `https://ai.pricememo.cn` and set `TRUSTED_PROXY_CIDRS` to the existing Caddy network CIDR.


## v3.2.0 database migration

After the v4 catalog migration, add the public correction fields before deploying the v3.2 API:

```bash
python scripts/migrate_productization_v5.py --database-url "$DATABASE_URL"
```

Deploy API and Web together, then smoke-test `/api/v1/corrections`, `/api/v1/watch.atom`, `/methodology`, `/watchlist` and the merchant Feed submission form. For remote merchant feeds, restrict importer egress at the container or network layer in addition to application URL validation.

## Shop intake and notification migration

After the v5 migration and before switching API/Web, run the idempotent v6 migration with the new API image:

```bash
python scripts/migrate_shop_intake_v6.py --database-url "$DATABASE_URL"
```

The migration creates `source_intakes` and `notification_outbox`, then converts historical `shop_request` Reports. Running it again is safe. Start the `notification-worker` service with the API stack; it is the only process allowed to call Resend or connect to SMTP. LDXP crawler and pipeline jobs receive `INTAKE_WORKER_KEY` and `INTAKE_API_URL`; the isolated detector receives only `DETECTOR_WORKER_KEY` and its API control URL.

Public submissions are asynchronous. The API saves `submitted` without contacting the URL, `source-detector` reports a detected platform, and an administrator reviews the resulting `pending_review` record. LDXP approval uses its queued crawler path. Dujiao-Next and Merchant JSON approval produces `approved`, which the authoritative publisher consumes; only a successful snapshot changes those records to `published`. Unknown `other` sources remain manual.

## Offer-history currency migration

Before switching an API version that reads `offer_history.currency`, run the idempotent v7 migration with the new API image:

```bash
python scripts/migrate_currency_v7.py --database-url "$DATABASE_URL"
```

The migration adds the history currency column and performs a conservative current-offer backfill from Merchant JSON raw records. It does not exchange-rate convert prices or rewrite historical observations whose original currency cannot be proven.

## Full multi-source publication

After the v7 currency migration, add the source detection fields and expanded intake constraints before switching the API:

```bash
python scripts/migrate_source_intake_v8.py --database-url "$DATABASE_URL"
```

The migration preserves legacy intake states, backfills existing declared/detected platforms, normalizes legacy `merchant_feed` rows to `merchant_json`, and merges same-URL conflicts before restoring the unique constraint. It is safe to run again. Rehearse it against a PostgreSQL 16 copy before production. After both migrations succeed, deploy API, Pipeline, Detector and Web from the same tested release, then run one complete publication:

```bash
python pipeline/publish_catalog.py \
  --ldxp-db /data/ldxp_crawler.db \
  --dujiao-db /data/ldxp_crawler.db \
  --merchant-sources /data/merchant_sources.json \
  --database-url "$DATABASE_URL"
```

The Dujiao database is the crawler SQLite containing `dujiao_candidates`; only approved and currently API-verified rows are selected. Omit `--merchant-sources` when no reviewed Merchant Feed configuration exists. Do not run individual Dujiao URLs as a production publication shortcut. If any connector fails, stop and investigate while the previous published snapshot remains active.

Required order for this release is: v7 migration, v8 migration, API, source detector, Pipeline, Web, then a successful full multi-source publication. Never switch an API that reads `offer_history.currency` or the new intake columns before its migration succeeds.
