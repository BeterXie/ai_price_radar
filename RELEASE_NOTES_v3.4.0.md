# AI Price Radar v3.4.0 — Community & Support

This release adds restrained community entry points while keeping production payment assets outside the public source repository.

## What changed

- The footer now links to the open-source repository and invites visitors to give the project a GitHub Star.
- Low-frequency prompts can introduce the GitHub repository after meaningful browsing and author support on later visits.
- Visitors can open an accessible support dialog and switch between WeChat Pay and Alipay QR codes.
- Community prompts do not auto-open on administrator or shop-submission routes.
- The support dialog does not display a payee name and does not record payment information.

## Deployment

- Rebuild and switch `api` and `web` from the same release commit.
- No database migration is required.
- Set `NEXT_PUBLIC_SUPPORT_ENABLED=true` and configure both public HTTPS QR URLs before building the Web application.
- Install `wechat.jpg` and `alipay.jpg` under production `data/support`; the Web container mounts this directory read-only at `/app/public/support`.
- Do not add payment QR images to the Git repository or GitHub Release assets.

## Compatibility

- Pricing, catalog, shop-intake, notification, crawler, and database behavior are unchanged.
- Author support remains optional and is hidden when its public configuration is disabled.
- Existing API clients remain compatible.
