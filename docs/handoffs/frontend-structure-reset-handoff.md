---
title: Frontend structure reset handoff
date: 2026-05-18
status: active
doc_type: handoff
area: frontend
task_tokens:
  - HRB-P1-07
related:
  - "[[decisions/frontend-page-composition-rules]]"
  - "[[lld/classic-to-react-admin-migration]]"
  - "[[features/ui-design-guidelines]]"
source_of_truth: true
---

# Контекст

`/app/ui-kit` удален из runtime вместе с route, sidebar entry, Vite input и template. Эксперимент признан неудачным: он не уменьшал хаос во frontend-страницах, а добавлял еще одну поверхность поддержки.

## Что изменено

- удален React entry `frontend/src/ui-kit/main.tsx`
- удален template `app/templates/react_ui_kit.html`
- удален route `GET /app/ui-kit`
- удален sidebar link из `app/templates/base.html`
- удален Vite input `ui-kit`
- удалены связанные docs про `ui-kit`
- добавлено решение `docs/decisions/frontend-page-composition-rules.md`
- `frontend/src/employees-list/` уже разрезан на:
  - `main.tsx`
  - `page.tsx`
  - `components.tsx`
  - `data.ts`
  - `types.ts`
- `frontend/src/scenario-workspace/` уже разрезан на:
  - `main.tsx`
  - `page.tsx`
  - `model.ts`
  - `pickers.tsx`
  - `sections.tsx`
  - `types.ts`

## Новый фокус

Главная проблема теперь зафиксирована явно:

- часть экранов перегружена в `main.tsx`
- `employee detail` уже переведен в `frontend/src/employee-detail/`, собран через Vite и разрезан на `main.tsx`, `page.tsx`, `sections.tsx`, `helpers.ts`
- `frontend/src/bulk-actions/` уже переведен с монолитного entrypoint на `main.tsx` (bootstrap-only) + `page.tsx`
- `frontend/src/settings/` тоже переведен с монолитного entrypoint на `main.tsx` (bootstrap-only) + `page.tsx`
- React templates уже не наследуют legacy `base.html`: добавлены `app/templates/react_base.html` и `app/static/react_shell.css` как отдельный shell для `/app/*` React routes
- В `tests/test_employee_api_smoke.py` добавлен parity smoke для employee detail, bulk-actions и settings workspace API
- Legacy operator entrypoints `/employees`, `/candidates`, `/bulk-actions`, `/flows`, `/surveys`, `/settings` уже переведены на redirect в React surfaces
- shared UI и page-level recipes расходятся по API

Следующий проход должен идти не через новую reference page, а через реальную реструктуризацию страниц.

## Что делать дальше

1. Пройтись по remaining classic fallback URLs и проверить, какие edit/list surfaces уже можно убирать без rollback gap.
2. Перед удалением каждого fallback держать parity smoke на критичных write-операциях зеленым.
3. Параллельно продолжить backend cleanup не “полным распилом”, а через `app/web/support.py` seam: employee support/model helpers уже вынесены в `app/web/employees.py`, а employee React/API routes уже вынесены в `app/web/employee_routes.py`.
4. `bulk-actions` уже вынесен на React/API уровне в `app/web/bulk_actions.py` + `app/web/bulk_action_routes.py`, `settings` — в `app/web/settings.py` + `app/web/settings_routes.py`, `scenario/surveys` React/API workspace — в `app/web/scenarios.py` + `app/web/scenario_routes.py`.
5. Следующий backend-проход уже не про новый workspace slice, а про cleanup remaining classic tails:
   - classic settings form handlers
   - classic scenario/survey editor routes и export
6. После этого уже добивать remaining shared Button/Select/Panel API и локальные page wrappers.
