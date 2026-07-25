# Validation report

Validated on 2026-07-25 with Python 3.11 and Node.js 20.

## Passed

- Python `compileall` for API, pipeline and crawler
- FastAPI tests: 39 passed（品牌分类边界、重分类清理、原始描述纯文本化、可信代理解析、举报限流与 429 响应）
- Pipeline tests: 27 passed（品牌分类边界、导入锁、人工审核状态保留、只读 SQLite 导入）
- FastAPI smoke test:
  - health endpoint
  - catalog endpoint
  - original-title keyword search
  - product detail
  - shop detail
  - admin-key rejection and acceptance
  - report submission
- LDXP crawler v2 self-test
- SQLite-to-website import test
- Repeated import idempotency test
- TypeScript/TSX syntax parse for all frontend source files
- JSON and Docker Compose YAML parse
- Shell script syntax checks
- Full Next.js production build and TypeScript validation
- Development and production Docker Compose config parsing
- Production preflight negative-path validation

## Production server validation (2026-07-26)

- Latest regression run: API 67 passed, pipeline 53 passed, frontend typecheck and production build passed.
- Deployed at `https://ai.pricememo.cn` through the server's existing Caddy instance.
- Let's Encrypt certificate issued successfully; HTTPS, HSTS, frame denial, MIME sniffing protection, and referrer policy verified.
- PostgreSQL, API, and Web containers are healthy and expose no host ports.
- Remote Python 3.13 test run: API 6 passed; pipeline 1 passed.
- Real PostgreSQL advisory-lock contention returned exit code 3 and wrote no test row.
- Repeated CSV import produced exactly one raw product, one offer, and one history row.
- Admin publish, public visibility, and hide-again workflow passed.
- Report submissions returned five 201 responses followed by 429 with `Retry-After: 3600`; validation reports were resolved and counters cleared.
- Backup created and restored into `price_radar_restore_test`; 8 public tables verified.
- Browser smoke test covered desktop/mobile homepage, catalog search/filter empty states, and admin entry. One invisible header CTA was found, fixed, redeployed, and reverified.
- Browser metrics during validation: TTFB 55 ms, FCP/LCP 184 ms, CLS 0.
- Remote Chromium full scan succeeded for 15/15 shops with 532 keyword matches and no blocked shops.
- Automatic SQLite validation, snapshot, and PostgreSQL sync imported 532 records with 0 failures.
- A systemd inventory run succeeded for 6/6 matched shops and synced 533 records with 0 failures (1 created, 7 changed).
- The existing hidden validation offer remained inactive, unapproved, and hidden after reimport.
- Public API returned 6 product categories after the production import.
- Enabled systemd schedules: inventory every 10 minutes, regular candidate scan hourly, and new-shop discovery every 12 hours.
- Imported 198 additional Wayback candidates into the production crawler database, increasing the candidate pool from 15 to 213 without overwriting the original candidates.
- First historical-candidate batch scanned 100/100 candidates: 99 completed scans, 1 blocked result, 2,680 keyword matches, and no circuit breaker. A second batch started automatically through the hourly schedule.
- Product-detail infinite scrolling now uses a real 30-item API page. Browser validation loaded 30 then 60 offers without console errors; the ChatGPT Plus initial response fell from about 1.19 MB to about 260 KB.
- Server-local read-only load testing remained error-free through 40 concurrent requests after pagination. The normal operating target is 10 concurrent uncached dynamic requests, with short bursts of 20 acceptable.
- The product-detail 60-second full-route cache returned `x-nextjs-cache: HIT`; at 10 concurrent cached requests, P95 was 151 ms with 49.7 RPS and no errors.

Recurring PostgreSQL backup scheduling and off-site retention still require production operations input.
