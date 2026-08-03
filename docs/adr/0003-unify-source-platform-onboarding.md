---
status: accepted
---

# Put every public store ecosystem through one source-platform onboarding protocol

Every platform uses the same lifecycle: passive public discovery or syntax-only submission, isolated fingerprint detection, pinned-IP public product retrieval, catalog classification, policy approval, atomic publication, and periodic revalidation. A platform adds only its bounded detector fingerprint, Connector, canonical identity and presentation label; it does not create a separate approval queue, publication path or direct database writer.

Automatically discovered candidates may receive policy approval only after their public contract and catalog-relevant products are verified. Public user submissions remain reviewable, and `rejected`, `disabled`, and `needs_re_review` are sticky states that discovery must not revive. Platforms that require credentials or merchant authorization, such as OAuth-only storefront APIs, need an explicit authenticated onboarding design and must not be impersonated by scraping private endpoints.

## Consequences

- Dujiao-Next, WooCommerce Store API, Merchant JSON and Schema.org Product/Offer sources share source-intake identities and the authoritative multi-source snapshot transaction.
- New ecosystems must use HTTPS 443, pinned validated public IPs, no redirects, and bounded per-response plus whole-source budgets before their records can reach classification.
- Passive search coverage can expand independently from Connector support, but a discovered URL never bypasses platform verification or catalog classification.
