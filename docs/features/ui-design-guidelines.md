---
title: UI/UX-гайдлайны
date: 2026-05-14
status: active
task_tokens:
  - HRB-P1-07
---

# UI/UX-гайдлайны

Документ фиксирует текущий UI-контракт для новых React-экранов. Попытка использовать отдельную `/app/ui-kit` страницу как source of truth была отменена: она не решила проблему хаоса в страницах и была удалена из runtime.

## UI stack

- React 18 + Vite
- Tailwind CSS v4
- shadcn/ui (base-nova) локально в `frontend/src/components/ui/*`
- Semantic theme tokens в `frontend/src/index.css`
- React shell/layout для `/app/*` страниц живет в `app/templates/react_base.html` и `app/static/react_shell.css`; legacy `base.html` и `app/static/styles.css` больше не должны быть implicit base для новых React screens.

Текущий факт по primitive layer:

- новые shadcn-компоненты из `base-nova` используют `@base-ui/react`;
- часть старых локальных wrappers еще Radix (`Popover`, `ScrollArea`);
- новые демо и новые UI-срезы должны следовать API реального компонента: `render` для Base UI, `asChild` только для Radix/Vaul wrappers.

## Базовый theme contract

Ключевая идея: компоненты красятся только через semantic tokens (`background`, `foreground`, `card`, `muted`, `primary`, `border`, `ring`).

### Темная палитра

- `background`: `#121212`
- `card`, `popover`: `#1D1D1F`
- `foreground`: `#E5E5E5`
- `muted-foreground`: `#8E8E93`
- `border`, `input`: `#38383A`
- `primary`, `accent`: `#93EB05`
- `destructive`: `#FF453A`
- `muted` / hover surface: `#2C2C2E`

### Светлая палитра

- `background`: `#FFFFFF`
- `card`, `popover`: `#FFFFFF`
- `foreground`: `#1D1D1F`
- `muted`: `#F5F5F7`
- `muted-foreground`: `#6E6E73`
- `border`, `input`: `#D8D8DC`
- `primary`, `accent`: `#93EB05`

### Жесткие правила темы

- `panel background` для outer wrappers всегда `transparent`.
- Тени отключены глобально (`shadow-*` не используются как визуальный сигнал).
- Focus ring нейтральный (`ring` не должен быть кислотно-зеленым).
- Компоненты не должны иметь hardcoded white/black фоны вместо semantic tokens.

## Foundation и поведение `div`

Каждый `div` должен выполнять одну роль: layout, semantic surface или grouping. Пустых декоративных wrapper без роли быть не должно.

### Layout rules

- Основной ритм: `gap-2`, `gap-3`, `gap-4`, `gap-6`, `gap-8`.
- Базовые секции: `rounded-* border border-border bg-card`.
- Outer shell/страничные контейнеры: `bg-transparent`.
- Вложенные demo/surface-блоки: `bg-card` или `bg-muted`.
- Радиусы только из токен-скейла (`rounded-sm ... rounded-2xl`), без случайных значений.

### Interaction rules

- Hover: только мягкое изменение surface (`bg-muted`/`bg-accent`), без резких эффектов.
- Focus-visible: стандартный library focus (token-based), без кастомных glow-эффектов.
- Active/selected состояния: border/tint через semantic colors.

## Структура React-страниц

Проблема проекта сейчас не в нехватке reference page, а в слабой композиции страниц.

Правило для новых и переписываемых экранов:

- `main.tsx` только bootstrap и mount.
- Корневой экран живет в `page.tsx` или `screen.tsx`.
- Крупные page-only блоки выносятся в локальный `components/`.
- Статические списки, табы, схемы полей и подписи не держатся в entrypoint, а лежат в `data.ts` или `config.ts`.
- Shared primitives продолжают жить в `frontend/src/components/ui/*`; page-level wrappers допустимы только если их еще нельзя честно поднять в shared слой.

Что это не значит:

- это не запрет на `shadcn/ui`, `Base UI` или другие уже принятые primitives;
- это запрет на огромные page-entry файлы, которые одновременно и bootstrap, и layout, и component library, и config blob.

## Явные проблемы, которые надо чинить

- Shared `Button` и реальные page usages уже расходятся по API (`danger` vs `destructive`).
- Primitive layer смешан между Base UI и legacy Radix wrappers.
- `employee detail` уже переведен в Vite/shared runtime и разрезан на `main.tsx + page.tsx + sections.tsx + helpers.ts`, но все еще тянет legacy visual patterns через собственный CSS и createElement-heavy sections.
- Новые React-экраны все еще частично пробиваются legacy-глобалями из `app/static/styles.css`.

## Legacy cleanup scope

При пересборке страниц нужно убрать зависимость новых React-экранов от старого глобального дизайна:

- `app/static/styles.css` содержит legacy tokens `--accent: #00a86b`, `--shadow`, `--bg-page`, `--bg-card`.
- В старом CSS есть глобальный `.grid`, который может конфликтовать с Tailwind-классами при неправильном порядке CSS.
- Старые страницы и временные React slices еще используют `--color-panel`, `--shadow-soft`, старые радиусы и gradient/shell treatment.
- React templates уже переведены на отдельный `react_base.html`, но при пересборке страниц все равно нужно проверять, что legacy CSS не пробивается через точечные classic partials, старые utility-классы и page-level one-off styles.

## Что запрещено

- Добавлять вторую компонентную библиотеку параллельно shadcn/ui.
- Рисовать цвета напрямую в компонентах вместо semantic tokens.
- Возвращать тени как основной depth-механизм.
- Использовать нестабильные кастомные `div`-паттерны вне foundation contract.

## Связанные файлы

- `frontend/src/index.css`
- `frontend/src/components/ui/*`
