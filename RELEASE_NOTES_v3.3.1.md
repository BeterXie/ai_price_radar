# AI Price Radar v3.3.1 — Linked Intake Notifications

This patch makes shop-intake notification emails actionable for administrators and applicants.

## What changed

- New shop-request emails sent to administrators include a direct link to the matching intake in the admin panel.
- The admin link contains only the intake identifier. Administrators must still enter the production admin key before data loads.
- After authentication, the admin panel scrolls to and highlights the intake referenced by the email.
- The final onboarding email sent to applicants includes the public shop page that was published by the successful import.

## Deployment

- Rebuild and switch `api`, `web`, and `notification-worker` from the same release commit.
- No database migration is required.
- Existing Resend configuration and the verified `notice@ai.pricememo.cn` sender remain unchanged.

## Compatibility

- Existing shop-intake states and API payloads are unchanged.
- Existing queued notifications keep their original email body; new notifications use the linked format.
- Public catalog and pricing behavior are unchanged.
