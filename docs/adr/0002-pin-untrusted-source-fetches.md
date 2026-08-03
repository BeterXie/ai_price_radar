---
status: accepted
---

# Pin every untrusted source fetch to a validated public IP

Source approval does not make a remote host trusted. Detector, catalog connectors and automatic discovery therefore share one HTTPS client instead of performing a DNS check followed by a separately resolved library request.

For each source sync, the client resolves the hostname once, rejects the complete answer set when any address is private, loopback, link-local, reserved, unspecified or multicast, and pins one validated numeric IP. Every connection uses that IP while TLS SNI, certificate verification and the HTTP `Host` header retain the original hostname. The client permits only HTTPS port 443, rejects redirects, streams bounded response bodies, and enforces per-response plus whole-source byte and wall-clock limits.

## Consequences

- DNS rebinding cannot change the destination between validation and connection or between requests in one source sync.
- `shared_http/` is installed into Detector, Pipeline and Crawler images; changing it requires rebuilding all three.
- DB-connected publication still has outbound network access. Host firewall or an egress proxy remains defense in depth if the threat model includes compromise of the fetching process itself.
