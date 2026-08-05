---
title: API-only Swagger/OpenAPI
date: 2026-06-01
status: accepted
doc_type: adr
area: backend
related:
  - "../api"
  - "../web-surface"
  - "../project_state"
source_of_truth: true
---

# API-only Swagger/OpenAPI

## Context

FastAPI already generates Swagger and OpenAPI automatically, but the HR Bot web surface is hybrid:

- JSON API routes under `/api/*`;
- React bootstrap pages under `/app/*`;
- classic HTML redirects and form handlers;
- file download/export routes;
- login/logout browser session routes.

Putting all of these into one Swagger document makes the schema noisy and weak as an API contract. It also encourages treating browser/form fallback routes as integration APIs, which conflicts with the current React migration direction.

## Decision

Swagger/OpenAPI is limited to JSON API routes under `/api/*`.

Non-API browser surfaces remain implemented and documented, but are hidden from OpenAPI via centralized route configuration in `app/main.py`.

Swagger UI is served by FastAPI at `/docs`; `/swagger` is a convenience alias redirecting to `/docs`.

The canonical split is:

- `docs/api.md` and `/docs` for JSON API contracts;
- `docs/web-surface.md` for non-JSON HTTP routes.

## Consequences

- `/docs` is useful for frontend/API development instead of being a full URL dump.
- Legacy fallback routes are less likely to become accidental public contracts.
- If a future team needs a full internal HTTP map, it should be added as a separate internal export, not by polluting API Swagger.
