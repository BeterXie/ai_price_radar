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

Browser watchlists are stored in localStorage. Atom Feed requests contain product slugs and optional target prices in the URL; the service does not create user profiles or persist subscriptions. Operators should avoid logging full query strings when they consider target prices sensitive.

## Source health and official references

Source-health values describe observable crawler success and failure facts, not reputation or fraud. Official list prices retain their source URL and verification date and are not converted into CNY or presented as a guarantee of local availability.
