# AI Price Radar v3.7.33 Release Notes

**Release Tag**: `v3.7.33`  
**Date**: 2026-09-04

## Summary

v3.7.33 delivers defense-in-depth security hardening against injection attacks on user-submitted store intake requests and email notifications.

## Key Security Improvements

1. **Email Header & CRLF Injection Prevention**:
   - Sanitized all email headers (`subject`, `recipient`, and `dedupe_key`) in both `source_intake.py` and `outbox.py`.
   - Strip all carriage returns, line feeds, tabs, and control characters (`[\r\n\t\x00-\x1f\x7f]`) from `shop_name`, `subject`, and outbound mail headers.
   - Enforced strict email recipient validation preventing multi-recipient injection, quote injection, and script tags.
2. **SSRF Hardening**:
   - `normalize_public_https_url` strictly forbids access to internal domains (`.local`, `.internal`, `.lan`, `.home`, `.corp`, `.intranet`, `.priv`, `.arpa`), loopback/private IPs (`127.0.0.1`, `0.0.0.0`, `169.254.169.254`, `::1`), and non-HTTPS schemes.
3. **Automated Security Verification**:
   - Added automated tests verifying CRLF sanitization, recipient rejection on invalid characters, and rejection of internal SSRF URLs.

## Verification

- `apps/api/tests`: 228 passed, 3 skipped.
- `detector/tests`: 68 passed, 1 skipped.
- `pipeline/tests`: 238 passed.
- `apps/web`: 55 passed.
