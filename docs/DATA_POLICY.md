# Data policy

The platform stores public product metadata only:

- shop name and source URL
- original product title
- price and stock status
- extracted delivery labels
- observation timestamps
- public shop listing requests and optional private applicant contact details

The platform must not store or publish:

- card codes or activation codes
- usernames and passwords
- customer email addresses
- order numbers
- payment details
- private chat logs

Risk flags are factual text extractions such as `无售后`, `无质保`, `售出不退`. They are not fraud scores and must not be displayed as an unsupported accusation.

Shops need a visible correction/report path. Removal should hide the offer publicly while retaining an audit record.

Applicant contact details are used only to review a shop listing request. They must not be displayed on public pages or included in public API responses.


## Public correction log

Only reports marked resolved and given an explicit public summary may appear in `/api/v1/corrections`. Raw report messages and applicant/reporter contact details remain private. A merchant response is published only when an administrator intentionally copies a response suitable for public display.

## Watchlists

Anonymous browser watchlists are stored in localStorage. Authenticated users persist product subscriptions, optional target prices, and email/QQ notification preferences in the service; the browser may keep an account-scoped cache. Anonymous items may be migrated into the signed-in account.

Atom Feed requests contain product slugs and optional target prices in the URL. Production reverse-proxy logging must omit the full request URI, and users should still treat personalized Feed URLs as sensitive links.

## Accounts, notifications, analytics, and logs

Email login stores the account email, session records, and bounded security metadata. QQ notification binding stores the receiving identifier and notification preferences. Login codes and outbound email/QQ payloads pass through the notification outbox and are removed according to the configured retention policy; expired login codes, binding sessions, and user sessions are also cleaned up.

When `NEXT_PUBLIC_GA_MEASUREMENT_ID` is configured, the web app offers an explicit browser-side analytics choice. GA4 is loaded only after opt-in, and account, admin, and authentication paths do not emit page-view events. The opt-out choice does not affect product functionality. Without that setting, GA4 is not loaded.

Application security, rate-limit, click, and activity records may include request timestamps, User-Agent values, session activity, and keyed IP hashes. These records are bounded by `PRIVACY_LOG_RETENTION_DAYS`; stale raw login IP values are cleared and expired transient records are deleted.

## Source health and official references

Source-health values describe observable crawler success and failure facts, not reputation or fraud. Official list prices retain their source URL and verification date and are not converted into CNY or presented as a guarantee of local availability.
