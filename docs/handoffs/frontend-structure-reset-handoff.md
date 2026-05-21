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
- React templates уже не наследуют legacy `base.html`: добавлены `app/templates/react_base.html` и `app/static/react_shell.css` как отдельный shell для `/app/*` React routes
- shared UI и page-level recipes расходятся по API

Следующий проход должен идти не через новую reference page, а через реальную реструктуризацию страниц.

## Что делать дальше

1. Пройтись по classic fallback routes и проверить, какие из них уже можно убирать без rollback gap.
2. После этого унифицировать shared Button/Select/Panel API по фактическим usages.
3. Перед удалением fallback routes сделать короткий parity-pass по критичным write-операциям.
