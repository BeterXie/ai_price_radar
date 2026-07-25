# Website integration

Crawler output database is imported by:

```bash
python ../../pipeline/sync_ldxp.py \
  --source-db ./ldxp_crawler.db \
  --database-url postgresql+psycopg://...
```

The website importer reads `matches` joined with `candidates`. It does not read card codes, orders or private credentials.
