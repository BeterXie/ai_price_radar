# AI Price Radar v3.3.0 — Shop Intake & Email Notifications

This release turns shop-submission review into a durable workflow and adds timely email notifications for administrators and applicants.

## What changed

- Store every shop request as a source-intake record with explicit review and validation states.
- Let administrators approve, reject, retry, and inspect notification delivery from the admin panel.
- Notify configured administrators when a request arrives and notify applicants when it is submitted, approved, rejected, validated, or published.
- Use Resend as the preferred production email provider while retaining SMTP for local Mailpit testing and fallback delivery.
- Deliver mail through a transactional outbox with idempotent processing and 1, 5, and 30 minute retry delays.
- Let LDXP crawler and pipeline jobs claim approved requests with a lease and report sanitized validation results.

## Production requirements

- Run `scripts/migrate_shop_intake_v6.py` before switching the API. The migration is idempotent and must first be exercised twice against a temporary PostgreSQL database.
- Start the `notification-worker` service alongside the API.
- Set a dedicated `INTAKE_WORKER_KEY` that differs from `ADMIN_API_KEY`.
- Configure `SHOP_INTAKE_ADMIN_EMAILS` and either:
  - `RESEND_API_KEY` plus a verified-domain `RESEND_FROM`, or
  - `SMTP_HOST` plus `SMTP_FROM` and any required SMTP credentials.
- Replace the `re_xxxxxxxxx` example with a newly generated real Resend API key only in the production `.env`; never commit it to Git.

## Compatibility

- Public catalog and pricing behavior are unchanged.
- Existing historical shop requests are converted by the v6 migration.
- No existing public pricing fields are removed.
