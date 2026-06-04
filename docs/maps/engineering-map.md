---
title: Engineering map
date: 2026-05-11
status: active
doc_type: map
area: docs
task_tokens:
  - HRB-DOC-03
related:
  - "[[README]]"
  - "[[architecture]]"
  - "[[api]]"
  - "[[data-model]]"
source_of_truth: false
---

# Engineering map

Навигация по инженерным документам. Эта карта не заменяет live docs.

## Architecture and runtime

- [[architecture]] — компоненты runtime, границы HTML routes, JSON API, bot ingress и scheduler jobs.
- [[configuration]] — env vars, defaults, secrets и stage placement.
- [[stage-deploy]] — GitHub Actions, SSH deploy, systemd services, smoke checks и backups.

## Backend/API

- [[api]] — полный JSON API из `app/main.py`.
- [[web-surface]] — classic HTML pages, form actions, downloads и redirects.
- [[features/scenario-engine]] — scenario templates, step types, branching, progress и launch behavior.
- [[features/notifications]] — текущая модель notifications и gaps.

## Data

- [[data-model]] — code-first schema, relationships, startup schema guard и observed SQLite drift.
- [[decisions/data-schema-source-of-truth]] — решение по code-first data schema truth.

## Frontend

- [[features/ui-design-guidelines]] — UI/UX принципы React admin surfaces.
- [[lld/classic-to-react-admin-migration]] — план переноса classic admin UI на React default, приоритет страниц и карта form routes для JSON API.
- Scenario workspace performance LLD пока не создан; кандидат описан в [[documentation-standard]].

## Bot

- [[features/bot-identity]] — Telegram identity/linking behavior и ограничения.
- [[features/employee-lifecycle]] — candidate/employee lifecycle и unresolved transitions.

## Documentation process

- [[documentation-standard]] — формат docs, LLD/ADR/runbook rules и Obsidian practices.
- [[decisions/documentation-format-standard]] — решение по легкому стандарту документации.
