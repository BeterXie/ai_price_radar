# Contributing

## Development checks

Before opening a pull request, run:

```bash
cd apps/api
python -m pytest -q

cd ../web
npm ci
npm run typecheck
npm run build
```

## Pull requests

- Keep each change focused.
- Add tests for classification, importing, pricing, or API behavior changes.
- Preserve source URLs and observation timestamps.
- Do not commit credentials, databases, browser profiles, production exports, or private user data.
- Explain the source, access frequency, and compliance boundary for each new connector.

## Price and risk rules

A rule may describe observable facts or statistical anomalies. It must not automatically label a shop as fraudulent without verifiable evidence.
