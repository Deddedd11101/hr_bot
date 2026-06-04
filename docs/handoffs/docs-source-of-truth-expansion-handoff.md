---
title: Передача контекста по расширению source of truth документации
date: 2026-05-11
status: active
task_tokens:
  - HRB-DOC-02
---

# Передача контекста по расширению source of truth документации

## Что добавлено

- Live-документация расширена за пределы первоначальных high-level vault docs.
- [[architecture]] обновлен так, чтобы оставаться верхнеуровневым и ссылаться наружу, а не впитывать каждый contract.
- Добавлены новые live docs:
  - [[api]]
  - [[web-surface]]
  - [[data-model]]
  - [[stage-deploy]]
  - [[configuration]]
- Обновлены [[README]], [[backlog]] и [[project_state]].
- Policy документации схемы записана в [[decisions/data-schema-source-of-truth]].

## Использованные источники

### Источники, подтвержденные репозиторием

- `app/main.py`
- `app/models.py`
- `app/database.py`
- `app/config.py`
- `.env.example`
- `.github/workflows/ci.yml`
- `.github/workflows/deploy-stage.yml`
- smoke tests в `tests/test_employee_api_smoke.py`

### Наблюдаемые runtime-источники

- local `hr_bot.db`
- previous stage notes в [[handoffs/telegram-linking-and-scope-handoff]]

## Важные находки

- JSON API surface больше, чем показывали ранние docs: он включает employee CRUD и React scenario workspace contract.
- У приложения нет чистого migration layer, хотя SQLAlchemy и Alembic dependencies есть в repo.
- `_ensure_sqlite_schema()` — major source of runtime truth и должен считаться частью schema contract.
- Live SQLite сейчас содержит unresolved drift:
  - `media_assets`
  - `flow_step_templates.media_asset_id`
- Current stage behavior частично documented only через operational handoff, а не infra-as-code.

## Что остается нерешенным

- Является ли `media_assets` dead subsystem, missing code commit или local/stage-only artifact.
- Должен ли stage дальше опираться на SQLite плюс manual DB replacement для scenario-heavy work.
- Остается ли `.env` precedence через `load_dotenv(override=True)` intended operational model для non-local environments.

## Рекомендуемые следующие шаги

1. Если schema work продолжится, проверить, нужно ли `media_assets` удалить, восстановить или формально закрепить за владельцем.
2. Если stage usage растет, codify server runtime явнее, а не полагаться на handoff-only truth.
3. Если React surfaces расширяются, обновлять [[api]] и [[web-surface]] в том же change.
