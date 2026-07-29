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
