---
title: Источник правды для схемы данных
date: 2026-05-11
status: accepted
task_tokens:
  - HRB-DOC-02
---

# Источник для схемы данных

## Решение

Документировать data model HR Bot так:

- code-first по `app/models.py`;
- с учетом startup schema behavior из `app/database.py`;
- live SQLite-only objects фиксировать отдельно как observed drift.

Не считать каждый объект, найденный в `hr_bot.db`, официальным subsystem contract автоматически.

## Контекст

- Проект использует SQLAlchemy-модели, но не имеет чистой migration chain.
- `_ensure_sqlite_schema()` меняет SQLite-схему на startup: добавляет tables, добавляет columns, пересоздает tables и нормализует старые значения.
- Инспекция текущего `hr_bot.db` уже показывает объекты, которых нет в active code: `media_assets` и `flow_step_templates.media_asset_id`.
- Если документация слепо отражает live SQLite, она может легализовать abandoned или half-removed structures как поддержанные.

## Выбранная модель

- Official live docs должны объяснять:
  - что ожидает текущий код;
  - что создает или patch-ит startup schema guard;
  - какой drift найден в live SQLite.
- Drift должен быть явно помечен как drift.
- Unsupported live DB objects не должны молча попадать в canonical architecture или API story.

## Последствия

### Плюсы

- Документация остается aligned с кодом, который реально запустится после следующего deploy.
- Live SQLite surprises становятся видимыми.
- Инженеры видят разницу между supported schema и accidental residue.

### Компромиссы

- При schema-relevant changes теперь надо проверять и code, и inspected SQLite file.
- “Просто покажи базу” звучит проще, но в этом репозитории такой ответ будет misleading.

## Следующие шаги

- Держать [[data-model]] актуальным после schema-relevant code changes.
- Если `media_assets` или другой drifted object все еще нужен, вернуть его как code-backed subsystem, а не оставлять undocumented.
