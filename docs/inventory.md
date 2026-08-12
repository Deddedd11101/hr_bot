---
title: Инвентаризация документации HR Bot
date: 2026-08-05
status: active
doc_type: map
area: docs
task_tokens:
  - HRB-DOC-03
related:
  - "[[README]]"
  - "[[documentation-standard]]"
  - "[[documentation-workflow]]"
  - "[[project_state]]"
  - "[[backlog]]"
source_of_truth: false
---

# Инвентаризация документации

Этот файл нужен для роли документоведа: быстро понять, какие документы являются каноном, какие являются навигацией или историей, и где есть риск устаревания.

Главное правило: если факт расходится между этим inventory и live doc, верить live doc. Inventory описывает ownership и актуальность, а не заменяет содержимое.

## Категории

| Категория | Назначение | Канонические файлы |
| --- | --- | --- |
| Agent entrypoint | Документы, с которых должен начинать агент перед работой. | [[README]], [[maps/start-here]], [[project_state]], [[backlog]], [[inventory]], [[documentation-workflow]], [[documentation-standard]] |
| Engineering source of truth | Runtime, API, web, data и configuration contracts. | [[architecture]], [[api]], [[web-surface]], [[data-model]], [[configuration]] |
| Pipelines and operations | Локальный запуск, stage deploy, smoke checks и delivery ledger. | [[local-runbook]], [[stage-deploy]], [[stage-change-log]] |
| Product and feature behavior | Поведение фич, риски и продуктовые ограничения. | [[features/bot-identity]], [[features/employee-lifecycle]], [[features/scenario-engine]], [[features/notifications]], [[features/scenario-portability]] |
| Frontend/UI governance | Правила React admin, shadcn/Base UI и page composition. | [[features/ui-design-guidelines]], [[features/shadcn-component-contract]], [[lld/classic-to-react-admin-migration]] |
| Decisions | Почему выбрана или отменена модель. | `decisions/` |
| Handoffs | Исторический контекст продолжения работы. Не канон. | `handoffs/` |
| Daily/history | Журнал хода работ. Не канон. | `daily/`, dated snapshot docs |
| Templates | Шаблоны для новых docs. | `templates/` |

## Live Docs

| Документ | Категория | Что проверять при аудите |
| --- | --- | --- |
| [[project_state]] | Agent entrypoint | Не превратился ли snapshot в длинный changelog; совпадают ли риски и ближайшие приоритеты с [[backlog]]. |
| [[backlog]] | Agent entrypoint | Статусы задач, task tokens, фактическая готовность и незакрытые discovery decisions. |
| [[architecture]] | Engineering source of truth | Совпадает ли с `app/main.py`, `app/web/*`, bot worker, scheduler и storage layout. |
| [[api]] | Engineering source of truth | Совпадает ли с текущими `/api/*` routes и fetch endpoints frontend. |
| [[web-surface]] | Engineering source of truth | Не описывает ли удаленные classic routes как живые; не теряет ли download/export/form fallback routes. |
| [[data-model]] | Engineering source of truth | Совпадает ли с `app/models.py`, `_ensure_sqlite_schema()` и known SQLite drift. |
| [[configuration]] | Engineering source of truth | Совпадает ли с `app/config.py`, `.env.example`, stage env precedence и secrets placement. |
| [[local-runbook]] | Pipelines and operations | Совпадает ли с реально рабочими локальными командами и текущим CI smoke набором. |
| [[stage-deploy]] | Pipelines and operations | Не путает ли repo-backed workflow reality, desired branch model и observed server state. |
| [[stage-change-log]] | Pipelines and operations | Есть ли запись после каждого stage deploy/config/db/infra изменения; нет ли локальных планов, выданных за выкатку. |
| [[documentation-standard]] | Agent entrypoint | Совпадает ли frontmatter contract с реальными документами и Obsidian practices. |
| [[documentation-workflow]] | Agent entrypoint | Не стал ли docs-процесс слишком тяжелым; правильно ли отделяет мелкие правки от contract changes. |

## Feature Docs

| Документ | Категория | Текущий статус аудита |
| --- | --- | --- |
| [[features/bot-identity]] | Product and feature behavior | Актуален по текущему `/start` identity flow: numeric ID first, затем public username fallback, candidate auto-create only on `/start`, blocked-user deny и interim username-based employee linking; OTP/linking invite остаются будущим решением. |
| [[features/employee-lifecycle]] | Product and feature behavior | Обновлен по explicit HR cutover `candidate -> adaptation` и manager assignment trigger; следующий аудит нужен при изменении lifecycle/event matrix. |
| [[features/scenario-engine]] | Product and feature behavior | В целом актуален по back-step, audience targeting и scheduler caveats; требует сверки при изменении transition-to-scenario semantics. |
| [[features/notifications]] | Product and feature behavior | Обновлен по `StepSendNotification` и legacy compatibility seam; следующий аудит нужен при финализации notification delivery rules. |
| [[features/scenario-portability]] | Product and feature behavior | Актуален как runbook-like feature doc; нужно обновлять при изменении `tools/scenario_portability.py`. |
| [[features/ui-design-guidelines]] | Frontend/UI governance | Актуален как UI policy; должен меняться вместе с `/app/design-system`, shared primitives и shell sidebar. |
| [[features/shadcn-component-contract]] | Frontend/UI governance | Актуален как жесткий frontend gate; проверять перед любыми shared UI/page composition правками. |

## Design And History Docs

| Документ/папка | Категория | Как читать |
| --- | --- | --- |
| [[lld/classic-to-react-admin-migration]] | Frontend/UI governance | Active LLD, но часть migration steps уже выполнена. Читать вместе с [[project_state]] и [[backlog]], а не как свежий snapshot сам по себе. |
| `decisions/` | Decisions | Исторический decision log. Решение может быть принято, но live behavior смотреть в feature/live docs. |
| `handoffs/` | Handoffs | Контекст на момент передачи. Может быть устаревшим даже при `status: active`; не использовать как source of truth без сверки. |
| `daily/` | Daily/history | Журнал, не канон. Полезен для восстановления последовательности событий. |
| [[roadmap-2026-05-12]] | Daily/history | Snapshot для показа, не текущий план работ. |
| [[demo-day-brief-2026-05-12]] | Daily/history | Личная шпаргалка демо, не продуктовый contract. |

## Текущие Documentation Risks

- Метаданные документов нормализованы под [[documentation-standard]]: все Markdown-файлы в `docs/` должны иметь `doc_type`, `area`, `status` и `source_of_truth`.
- В `decisions/` используется стандартный `doc_type: adr`. Новые decision records создавать только в этом формате.
- Handoff-файлы не должны быть `source_of_truth: true`. Если handoff содержит актуальный факт, его нужно перенести в live doc и оставить handoff историей.
- Active LLD по classic-to-React migration уже частично стал историческим планом. Его нельзя читать без [[project_state]].
- Stage deploy docs имеют два слоя truth: repo-backed workflow behavior и desired stage/integration branch model. При аудите нельзя автоматически считать желаемую модель уже enforced в GitHub Actions.
- Daily notes и handoff templates не должны становиться обязательным ритуалом. По умолчанию использовать live docs; daily только для насыщенных operational days, handoff только при реальной передаче контекста.

## Рекомендуемый Порядок Аудита

1. Проверить `git status --short`, чтобы не смешать документационный аудит с чужой работой.
2. Читать [[project_state]], [[backlog]], [[documentation-workflow]], [[documentation-standard]].
3. Проверить changed docs against this inventory.
4. Для runtime/API/data/deploy фактов сверить соответствующий live doc с кодом или workflow.
5. Если обнаружен актуальный факт только в handoff/daily, перенести его в live doc.
6. Если обнаружен устаревший active doc, либо обновить его, либо явно пометить как `superseded`/historical и указать replacement.
