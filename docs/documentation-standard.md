---
title: Стандарт документации HR Bot
date: 2026-05-11
status: active
doc_type: standard
area: docs
task_tokens:
  - HRB-DOC-03
related:
  - "[[README]]"
  - "[[backlog]]"
  - "[[project_state]]"
  - "[[decisions/documentation-format-standard]]"
source_of_truth: true
---

# Стандарт документации HR Bot

Этот стандарт описывает, как вести `docs/` как git-backed Obsidian vault без превращения документации в отдельную систему поверх репозитория.

Главное правило: Markdown-файлы в git являются каноном. Obsidian дает навигацию, свойства, backlinks, graph, templates и canvas, но не хранит отдельную правду.

## Типы документов

| `doc_type` | Назначение | Source of truth |
| --- | --- | --- |
| `map` | Навигационная карта по vault или области. Не дублирует факты, а ведет к каноническим файлам. | `false` |
| `state` | Текущий snapshot состояния проекта, рисков и ближайших приоритетов. | `true` |
| `backlog` | Канонический список задач, статусов и task tokens. | `true` |
| `architecture` | High-level runtime topology, boundaries, подсистемы и data flows. | `true` |
| `lld` | Low-level design для значимых изменений подсистемы или контракта. | `true` для активного LLD |
| `feature` | Поведение конкретной функциональной области. | `true` если описывает актуальное поведение |
| `api` | Реализованные HTTP/API контракты. | `true` |
| `data` | Схема данных, отношения, migration/schema-guard behavior и drift. | `true` |
| `runbook` | Операционные инструкции, deploy, smoke checks, rollback. | `true` |
| `adr` | Принятое или отмененное архитектурное/продуктовое решение. | `true` как historical decision record |
| `handoff` | Контекст передачи работы после сессии или крупного изменения. | `false` |
| `daily` | Дневная заметка, журнал или краткий operational note. | `false` |
| `standard` | Правила ведения документации. Используется для этого файла. | `true` |

## Frontmatter contract

Новые и существенно обновленные документы должны иметь Properties:

```yaml
---
title: Название документа
date: YYYY-MM-DD
status: active
doc_type: feature
area: backend
task_tokens:
  - HRB-...
related:
  - "[[project_state]]"
source_of_truth: true
---
```

Допустимые `status`:

- `active` — актуальный live-документ.
- `draft` — черновик, не использовать как канон без проверки.
- `accepted` — принятое решение или утвержденный дизайн.
- `archived` — исторический контекст, не актуальный контракт.
- `superseded` — заменено другим документом; ссылка на replacement обязательна в тексте.

Допустимые `area`:

- `core`
- `backend`
- `frontend`
- `bot`
- `data`
- `deploy`
- `docs`
- `product`

`review_after` опционален, но желателен для `runbook`, deploy/config docs и документов, которые зависят от внешнего server state.

## Что является live source of truth

Основные live docs:

- [[project_state]] — состояние проекта и риски.
- [[backlog]] — задачи, статусы и task tokens.
- [[architecture]] — runtime architecture и границы подсистем.
- [[api]] — реализованный JSON API.
- [[web-surface]] — non-JSON operator web surface.
- [[data-model]] — текущая схема данных и drift.
- [[stage-deploy]] — stage deploy/runbook.
- [[configuration]] — env/config contract.

Historical docs:

- `decisions/` фиксируют, почему решение было принято.
- `handoffs/` фиксируют состояние на момент передачи.
- `daily/` помогает восстановить ход работ, но не заменяет live docs.

## Когда создавать LLD

LLD нужен только если изменение затрагивает устройство подсистемы или контракт. Не надо писать LLD для косметики, copy changes или очевидного bugfix без изменения модели.

LLD обязателен или очень желателен, если меняется:

- schema/data model или migration behavior;
- public/internal API contract;
- runtime flow между admin, bot, scheduler и database;
- bot identity/linking model;
- deploy или rollback path;
- scheduler behavior;
- scenario engine semantics;
- notification model;
- React workspace architecture.

Минимальный формат LLD:

1. Контекст
2. Цель
3. Текущее состояние
4. Предлагаемое устройство
5. Data flow
6. API / schema / interfaces
7. Edge cases
8. Тестирование
9. Rollout / rollback
10. Открытые вопросы

Первые кандидаты на LLD:

- scenario engine;
- bot identity;
- employee lifecycle;
- notification model;
- schema/migration strategy;
- React scenario workspace.

## Когда создавать ADR

ADR нужен, когда решение:

- задает долгосрочное направление;
- меняет архитектурную границу;
- фиксирует trade-off;
- отменяет прежнюю модель;
- важно для будущих ревью и onboarding.

ADR не обязан быть большим. Важнее явно записать контекст, решение, последствия и ссылки на связанные live docs.

## Obsidian practices

Использовать:

- Properties для фильтрации по `doc_type`, `area`, `status`, `source_of_truth`.
- Backlinks и wiki-links для связи live docs, ADR, feature docs и handoffs.
- Graph как navigation и sanity-check связности.
- Templates plugin для новых LLD/ADR/runbook/feature/handoff/daily notes.
- Canvas для схем потоков, например scenario execution или candidate-to-employee lifecycle.
- Bookmarks для стартовых карт и основных live docs.

Эти практики опираются на core Obsidian plugins. Единственный обнаруженный community plugin — `obsidian-kanban`; стандарт не требует новых community plugins.

Не использовать:

- Kanban как отдельный backlog. Канон остается [[backlog]].
- Canvas как замену Markdown-документа. Canvas должен ссылаться на docs.
- Graph как основной способ чтения документации.
- `.obsidian/` как место для канонических знаний о проекте.

## Правило обновления

Если меняется код, архитектура, deploy, schema, API, operational behavior или статус задачи:

1. Обновить live doc соответствующей области.
2. Обновить [[backlog]], если изменился статус задачи.
3. Обновить [[project_state]], если изменились состояние, риски или приоритеты.
4. Добавить ADR, если принято значимое решение.
5. Добавить handoff, если после работы нужен устойчивый контекст для продолжения.

Не надо дублировать один и тот же факт в пяти местах. Live doc хранит факт, maps и handoffs только ссылаются на него.
