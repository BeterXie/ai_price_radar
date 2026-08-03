---
status: accepted
---

# Isolate untrusted source detection from the public API

The public API records syntax-valid source submissions but never dereferences user-controlled URLs. A dedicated detector with no database or internal-service network access performs bounded HTTPS-only probes through a pinned, previously validated public IP and reports results over a narrow authenticated API; this trades immediate detection for removal of the API process's SSRF and DNS-rebinding window.

## Consequences

Detection is asynchronous, so a submission remains `submitted` until the detector reports `pending_review` or `validation_failed`. Approval and publication remain separate transitions, and the detector cannot publish catalog data.
