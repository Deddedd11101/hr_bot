---
title: Stage admin HTTPS baseline
date: 2026-07-01
status: accepted
doc_type: adr
area: deploy
related:
  - "[[stage-deploy]]"
  - "[[backlog]]"
  - "[[configuration]]"
source_of_truth: true
---

# Stage admin HTTPS baseline

## Context

Stage admin currently has been observed as reachable directly on `http://92.51.38.32:8000/...`.
That is acceptable for early internal debugging, but it is not a good baseline for real HR/admin use because login credentials and session cookies should not travel over plain HTTP.

## Decision

Use a simple domain + HTTPS reverse proxy baseline for stage admin:

- buy or assign a normal domain/subdomain, for example `admin.<domain>`;
- point DNS `A` record to `92.51.38.32`;
- run Caddy on the stage server as reverse proxy on ports `80/443`;
- proxy traffic to FastAPI on `127.0.0.1:8000`;
- close public access to port `8000`;
- set `ADMIN_SESSION_COOKIE_SECURE=true` after HTTPS is live;
- rotate `ADMIN_SESSION_SECRET` during the same operational change.

Do not start with VPN-only as the default. VPN-only can be added later if the access group is tiny and operationally ready for it. The first pragmatic security step is HTTPS + no direct public app port.

## Deferred Hardening

Possible follow-up layers:

- IP allowlist in Caddy or firewall;
- Basic Auth at the proxy as a temporary second factor;
- formal audit/session management in the app;
- broader security/compliance pass for files, personal data, roles, and CSRF.
