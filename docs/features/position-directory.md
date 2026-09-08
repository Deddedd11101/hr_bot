---
title: Справочник должностей
date: 2026-09-08
status: active
doc_type: feature
area: data
related:
  - "[[data-model]]"
  - "[[features/scenario-engine]]"
  - "[[decisions/2026-07-22-managed-positions-catalog]]"
source_of_truth: true
---

# Справочник должностей

`positions` — активный каталог для employee forms, scenario role scope, bot-menu targeting и bulk targeting. Канонический набор стартовых значений хранится в `app/positions.py::CANONICAL_POSITION_TITLES`. При старте приложения каталог дополняется только этим набором: значения из `employees.desired_position` больше не создают новые position rows автоматически.

`employees.desired_position` остается строкой. Это намеренная compatibility boundary: существующие карточки и старые сценарии не переписываются при старте. Unknown/current employee value может временно попасть в options конкретной карточки, но не становится новым каталогом и не создает новую position row при сохранении карточки.

## Источники значений

- startup seed: `seed_positions_catalog()`;
- ручной CRUD: `/api/settings/positions*`;
- employee detail update: `resolve_employee_position_value()` сохраняет неизвестное значение в строковом поле без auto-create каталога;
- bot scenario answers: direct write в `scenario_engine.py`;
- stage/import tools: `tools/import_stage_employees.py`;
- runtime matching: `position_matches_scope()` и `scenario.role_scope`.

## Audit и согласованные замены

Read-only отчет по карточкам и catalog drift:

```powershell
.\.venv\Scripts\python.exe tools\audit_positions.py --db .\hr_bot.db
```

`tools/audit_positions.py` не вызывает schema patching и открывает SQLite в read-only режиме. Для неоднозначных значений `proposed_mapping` остается пустым; автоматическое объединение не выполняется.

Явные замены по согласованному mapping сначала выполняются в dry-run:

```powershell
.\.venv\Scripts\python.exe tools\replace_positions.py --db .\hr_bot.db --mapping "OLD=Каноническая должность" --update-scopes
```

`--apply` разрешен только с `--backup-dir`: инструмент сначала создает SQLite backup, затем в одной транзакции обновляет exact employee values. `--update-scopes` дополнительно обновляет только явно совпавшие slugs в scenario/menu/bulk targeting; без этого флага role scopes не меняются.

Нельзя удалять `positions` rows как способ cleanup: сначала нужен согласованный mapping и проверка сценариев/targeting, затем отдельный backup-backed apply.
