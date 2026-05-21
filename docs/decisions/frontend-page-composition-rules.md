---
title: Frontend page composition rules
date: 2026-05-18
status: accepted
doc_type: decision
area: frontend
task_tokens:
  - HRB-P1-07
related:
  - "[[lld/classic-to-react-admin-migration]]"
  - "[[features/ui-design-guidelines]]"
  - "[[architecture]]"
source_of_truth: true
---

# Решение

Для React-админки `main.tsx` больше не считается местом для сборки всей страницы. Entry-файл отвечает только за bootstrap и mount.

## Почему

Проблема фронта сейчас не в отсутствии еще одной UI-витрины, а в слабой композиции экранов:

- крупные `main.tsx` смешивают bootstrap, layout, page-only components и config;
- это раздувает контекст, усложняет рефакторинг и делает новые страницы дорогими;
- до недавнего времени `employee detail` жил отдельным legacy JS/CSS слоем; сам перенос в Vite не решил проблему автоматически, потому что крупный page-монолит так же токсичен, как крупный `main.tsx`.

## Что принято

- `main.tsx` только монтирует приложение.
- Корневой экран страницы живет в `page.tsx` или `screen.tsx`.
- Крупные локальные блоки живут в соседнем `components/`.
- Статические схемы, меню, tab definitions и field configs не хранятся в entrypoint, а уходят в `data.ts` или `config.ts`.
- Shared primitives можно продолжать строить на `shadcn/ui`, `Base UI` и текущем stack; это решение не про отказ от библиотек, а про дисциплину композиции.

## Что отвергнуто

- Продолжать делать новые страницы как один большой `main.tsx`.
- Маскировать архитектурную проблему demo/reference page вроде `/app/ui-kit`.
- Поднимать page-level recipe в shared слой до появления устойчивого общего API.
