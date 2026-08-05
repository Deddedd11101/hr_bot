---
title: Карта документации HR Bot
date: 2026-05-12
status: active
doc_type: map
area: docs
task_tokens:
  - HRB-DOC-01
  - HRB-DOC-02
  - HRB-DOC-03
  - HRB-DOC-04
related:
  - "[[documentation-standard]]"
  - "[[maps/start-here]]"
  - "[[backlog]]"
  - "[[project_state]]"
source_of_truth: true
---

# Документация HR Bot

`docs/` — корень проектной документации и рекомендуемый Obsidian vault для HR Bot.

Эта папка намеренно остается обычным Markdown:

- те же файлы читаются в Obsidian, git и обычных редакторах;
- Markdown-файлы являются source of truth;
- Obsidian — UI поверх этих файлов, а не отдельное хранилище;
- `.obsidian/` — локальное состояние редактора, не каноническая документация.

## С чего начинать

1. Открой [maps/start-here.md](/D:/HRBot/hr_bot/docs/maps/start-here.md), если нужен быстрый вход через Obsidian.
2. Прочитай [project_state.md](/D:/HRBot/hr_bot/docs/project_state.md), чтобы понять текущие риски и приоритеты.
3. Открой [backlog.md](/D:/HRBot/hr_bot/docs/backlog.md), если работа связана с задачей или статусом.
4. Прочитай [architecture.md](/D:/HRBot/hr_bot/docs/architecture.md), если изменение затрагивает runtime или границы подсистем.
5. Используй [documentation-standard.md](/D:/HRBot/hr_bot/docs/documentation-standard.md), когда создаешь новый документ, ADR, LLD, runbook или handoff.

## Основные live docs

Эти документы не равноправны с daily/handoff заметками: они являются текущим рабочим source of truth.

| Документ | Назначение |
| --- | --- |
| [project_state.md](/D:/HRBot/hr_bot/docs/project_state.md) | Текущее состояние системы, риски, ограничения и ближайшие приоритеты. |
| [backlog.md](/D:/HRBot/hr_bot/docs/backlog.md) | Канонический список задач, task tokens и статусов. |
| [inventory.md](/D:/HRBot/hr_bot/docs/inventory.md) | Инвентаризация docs по категориям, source-of-truth статусу и рискам устаревания. |
| [documentation-workflow.md](/D:/HRBot/hr_bot/docs/documentation-workflow.md) | Практический gate: когда docs нужны, когда нет, и куда писать изменения. |
| [architecture.md](/D:/HRBot/hr_bot/docs/architecture.md) | Runtime topology, boundaries, подсистемы и high-level data flows. |
| [api.md](/D:/HRBot/hr_bot/docs/api.md) | Реализованный JSON API для React-экранов и scenario workspace. |
| [web-surface.md](/D:/HRBot/hr_bot/docs/web-surface.md) | Classic HTML pages, form actions, downloads, exports и redirects. |
| [data-model.md](/D:/HRBot/hr_bot/docs/data-model.md) | Текущая модель данных по коду, startup schema guard и observed SQLite drift. |
| [local-runbook.md](/D:/HRBot/hr_bot/docs/local-runbook.md) | Локальный запуск админки, bot worker и пересборка frontend assets. |
| [stage-deploy.md](/D:/HRBot/hr_bot/docs/stage-deploy.md) | Stage deploy path, runbook, smoke checks и границы repo-vs-server truth. |
| [stage-change-log.md](/D:/HRBot/hr_bot/docs/stage-change-log.md) | Журнал того, что реально выведено и проверено на test/stage. |
| [configuration.md](/D:/HRBot/hr_bot/docs/configuration.md) | Environment variables, precedence rules, secrets и stage placement. |

## Навигационные карты

Maps помогают читать vault, но не хранят факты вместо live docs.

| Карта | Для чего |
| --- | --- |
| [maps/start-here.md](/D:/HRBot/hr_bot/docs/maps/start-here.md) | Входная карта для нового читателя. |
| [maps/engineering-map.md](/D:/HRBot/hr_bot/docs/maps/engineering-map.md) | Backend, frontend, bot, data, deploy и documentation links. |
| [maps/product-map.md](/D:/HRBot/hr_bot/docs/maps/product-map.md) | Lifecycle, identity, notifications и scenario behavior. |

## Демо и roadmap snapshots

Snapshot-документы удобны для демо, handoff и обсуждения планов, но не заменяют live docs.

| Документ | Для чего |
| --- | --- |
| [roadmap-2026-05-12.md](/D:/HRBot/hr_bot/docs/roadmap-2026-05-12.md) | Roadmap для показа: что сделано, что стабилизируем, план по модулям, отпуска, разделение данных двух ИП и Telegram Mini Apps. |
| [demo-day-brief-2026-05-12.md](/D:/HRBot/hr_bot/docs/demo-day-brief-2026-05-12.md) | Личная шпаргалка демо-дня: порядок показа, talk track, что проговорить и что не обещать без уточнения. |

## Типы документов

Полный стандарт описан в [documentation-standard.md](/D:/HRBot/hr_bot/docs/documentation-standard.md).

| `doc_type` | Когда использовать | Канон |
| --- | --- | --- |
| `map` | Навигация по vault или области. | Нет |
| `state` | Snapshot проекта, риски, приоритеты. | Да |
| `backlog` | Задачи, статусы, task tokens. | Да |
| `architecture` | Runtime topology и границы подсистем. | Да |
| `lld` | Значимое изменение подсистемы или контракта. | Да, если активный |
| `feature` | Поведение конкретной функциональной области. | Да, если актуальный |
| `api` | HTTP/API контракты. | Да |
| `data` | Схема данных, relations, schema guard, drift. | Да |
| `runbook` | Deploy, операции, smoke checks, rollback. | Да |
| `adr` | Принятое или отмененное решение. | Да как decision record |
| `handoff` | Передача контекста после работы. | Нет |
| `daily` | Дневной журнал. | Нет |
| `standard` | Правила ведения документации. | Да |

## Feature docs

- [features/scenario-engine.md](/D:/HRBot/hr_bot/docs/features/scenario-engine.md) — scenario engine, типы шагов и execution rules.
- [features/notifications.md](/D:/HRBot/hr_bot/docs/features/notifications.md) — модель уведомлений и known gaps.
- [features/employee-lifecycle.md](/D:/HRBot/hr_bot/docs/features/employee-lifecycle.md) — candidate/employee lifecycle, stages и missing transitions.
- [features/bot-identity.md](/D:/HRBot/hr_bot/docs/features/bot-identity.md) — Telegram identity/linking behavior и риски.
- [features/scenario-portability.md](/D:/HRBot/hr_bot/docs/features/scenario-portability.md) — export/import сценариев между SQLite environments.
- [features/ui-design-guidelines.md](/D:/HRBot/hr_bot/docs/features/ui-design-guidelines.md) — UI/UX-принципы для React admin surfaces.

## Templates

Шаблоны лежат в [templates](/D:/HRBot/hr_bot/docs/templates) и совместимы с обычным Markdown и Obsidian Templates plugin.

| Template | Для чего |
| --- | --- |
| [templates/lld-template.md](/D:/HRBot/hr_bot/docs/templates/lld-template.md) | Low-level design для значимых изменений. |
| [templates/adr-template.md](/D:/HRBot/hr_bot/docs/templates/adr-template.md) | Decision note. |
| [templates/runbook-template.md](/D:/HRBot/hr_bot/docs/templates/runbook-template.md) | Операционный runbook. |
| [templates/feature-template.md](/D:/HRBot/hr_bot/docs/templates/feature-template.md) | Feature behavior doc. |
| [templates/handoff-template.md](/D:/HRBot/hr_bot/docs/templates/handoff-template.md) | Передача контекста. |
| [templates/daily-template.md](/D:/HRBot/hr_bot/docs/templates/daily-template.md) | Daily note. |

## Исторические документы

- [decisions](/D:/HRBot/hr_bot/docs/decisions) — ADR-style decision log.
- [handoffs](/D:/HRBot/hr_bot/docs/handoffs) — снимки состояния для продолжения работы.
- [daily](/D:/HRBot/hr_bot/docs/daily) — короткие daily notes, которые не заменяют live docs.

## Obsidian practices

- Используй Properties для фильтрации по `doc_type`, `area`, `status`, `source_of_truth`.
- Используй backlinks и wiki-links для связей между live docs, ADR, feature docs и handoffs.
- Graph используй как navigation и sanity-check связности, а не как основной способ чтения.
- Canvas используй только для схем потоков; canvas должен ссылаться на Markdown docs, а не заменять их.
- Kanban не использовать как отдельный backlog. Канонический backlog — [backlog.md](/D:/HRBot/hr_bot/docs/backlog.md).
- Новый стандарт не требует community plugins сверх уже установленного `obsidian-kanban`; Templates, Properties, Graph, Canvas, Backlinks и Bookmarks — core Obsidian plugins.

## Рабочие правила

- Используй task tokens вроде `HRB-P0-01` прямо в документах и decisions.
- Wiki-links можно использовать внутри vault, но текст должен оставаться читаемым вне Obsidian.
- Для аудита актуальности начинай с [inventory.md](/D:/HRBot/hr_bot/docs/inventory.md), но не считай его заменой live docs.
- Перед созданием новых docs проверь [documentation-workflow.md](/D:/HRBot/hr_bot/docs/documentation-workflow.md): мелкие правки без contract change обычно не документируются.
- Если решение изменилось, обнови live document и добавь новую note в `decisions/`.
- Если задача началась или завершилась, обнови [backlog.md](/D:/HRBot/hr_bot/docs/backlog.md).
- Если изменился operational context, обнови [project_state.md](/D:/HRBot/hr_bot/docs/project_state.md).
- Если изменилась implementation model, обнови [architecture.md](/D:/HRBot/hr_bot/docs/architecture.md) или relevant feature doc.

## Реализованные documentation tasks

| Token | Результат |
| --- | --- |
| `HRB-DOC-01` | `docs/` структурирован как project vault с live docs и dated history. |
| `HRB-DOC-02` | Добавлены live docs для JSON API, web surface, data model, stage deploy и configuration. |
| `HRB-DOC-03` | Введены documentation standard, templates, navigation maps и правило Obsidian-as-navigation-layer. |
