---
status: accepted
---

# Isolate untrusted source detection from the public API

The public API records syntax-valid source submissions but never dereferences user-controlled URLs. A dedicated detector without database credentials or membership in the default application network performs bounded HTTPS-only probes through a pinned, previously validated public IP and reports results over a narrow authenticated API; this trades immediate detection for removal of the API process's SSRF and DNS-rebinding window.

## Consequences

Detection is asynchronous, so a submission remains `submitted` until the detector reports `pending_review` or `validation_failed`. Approval and publication remain separate transitions, and the detector cannot publish catalog data.

The Compose topology gives the detector two dedicated networks. `detector_control` is internal and contains only the detector and API, while `detector_egress` supplies outbound connectivity without attaching the detector to the database/default or frontend networks. The detector receives only its dedicated API key, uses no volumes, runs as an unprivileged user with all capabilities dropped, and has no Docker socket.

Compose bridge networks do not express destination-port firewall policy. Port 443 enforcement, public-address rejection, redirect refusal, response limits, and TLS connections to a validated numeric IP are therefore application-layer controls. A compromised detector process could bypass those controls and use other outbound ports; deployments requiring containment against detector-code compromise must add a host firewall or egress proxy that allows only public TCP/443 while preserving access to the detector control API. The current boundary protects the public API from user-controlled URL dereferencing and prevents submitted URLs from reaching internal addresses; it is not claimed to be a complete sandbox for hostile detector code.
