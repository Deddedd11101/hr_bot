---
title: UI/UX-гайдлайны
date: 2026-05-14
status: active
doc_type: feature
area: frontend
task_tokens:
  - HRB-P1-07
related:
  - "[[features/shadcn-component-contract]]"
  - "[[lld/classic-to-react-admin-migration]]"
  - "[[decisions/frontend-page-composition-rules]]"
source_of_truth: true
---

# UI/UX-гайдлайны

Документ фиксирует текущий UI-контракт для новых React-экранов. Отдельная `/app/ui-kit` витрина действительно была неудачным экспериментом и удалена из runtime, но это не отменяет потребность в живом source of truth: теперь эту роль должен выполнять `/app/design-system` как baseline реальных shared primitives, page patterns и review rules.

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

- `background`: `#141412`
- `card`, `popover`: `#1C1B18`
- `foreground`: `#F5F3EF`
- `muted`: `#252420`
- `muted-foreground`: `#8C8880`
- `border`, `input`: `#2E2C28`
- `primary`: `#4AAD7A`
- `accent`: `#113824`
- `destructive`: `#EF4444`

### Светлая палитра

- `background`: `#FAFAF9`
- `card`, `popover`: `#FFFFFF`
- `foreground`: `#1A1916`
- `muted`: `#F5F4F2`
- `muted-foreground`: `#6B6963`
- `border`, `input`: `#E8E6E1`
- `primary`: `#339160`
- `accent`: `#F0FAF4`

### Жесткие правила темы

- `panel background` для outer wrappers всегда `transparent`.
- Тени запрещены как механизм глубины для поверхностей **в потоке**: карточек, модулей, панелей. Там глубину дают контраст, рамка и отступы.
- Для слоёв, **всплывающих над страницей** — выпадающий список, поповер, меню, диалог, шторка — тень обязательна: собственного фона им не хватает, `--popover` и `--card` совпадают в обеих темах. Возвышение задаётся токеном `--shadow-overlay` и идёт вместе с рамкой. Это продуктовое решение от 26.08.2026, а не молчаливая правка locked baseline.
- Focus ring идет через primary palette, без случайных сторонних цветов.
- Компоненты не должны иметь hardcoded white/black фоны вместо semantic tokens.
- Эта палитра считается locked baseline. Не менять без явного продуктового решения.

## `/app/design-system` как live baseline

`/app/design-system` теперь должен быть не декоративной презентацией, а рабочим эталоном для frontend-решений.

Минимальный состав baseline:

- `Foundations`: semantic tokens, type scale, spacing, radius, policy по depth/shadows.
- `Primitives`: реальные shared UI API (`Button`, `Input`, `Textarea`, `Select`, `Checkbox`, `Switch`, `Badge`, `Card`, `Table`, `Breadcrumb`, `Tabs`, `Dialog`, `Dropdown`, `Tooltip`, `Progress`, `Avatar`, `Skeleton`).
- `Patterns`: repeatable operator layouts (`list`, `detail`, `settings`, `workspace`).
- `Review rules`: явные anti-patterns и checklist для ручного review и будущего watchdog.

Жесткое правило:

- если новый экран нельзя объяснить через primitives и patterns из `/app/design-system`, это не “гибкость”, а сигнал о drift или дыре в shared API.

## Shell sidebar contract

Глобальный sidebar для `/app/*` страниц живет не в React component catalog, а в shell-слое:

- markup: `app/templates/react_base.html`
- styling: `app/static/react_shell.css`

Это не исключение из дизайн-системы, а часть UI contract. Для shell sidebar действуют отдельные жесткие правила:

- он использует ту же locked palette, что и React UI;
- он остается структурным и нейтральным, без glossy gradients и кислотных accent-hover паттернов;
- hover не должен менять геометрию элемента скачком;
- active state строится через soft accent tint и border, а не через тень или агрессивный pill morph;
- expand/collapse анимация должна быть плавной и предсказуемой, без нервного схлопывания на микродвижении курсора;
- sidebar открывается только явным trigger, а не hover-hotzone или auto-peek логикой;
- expanded panel всегда overlay поверх content и не имеет права сдвигать рабочую область страницы;
- nav click не должен мгновенно схлопывать sidebar при переходе между `/app/*` страницами; выбранный раздел должен оставаться раскрытым через навигацию;
- dark mode обязан поддерживаться на том же уровне, что и page content.

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

- Shared `Button` и реальные page usages уже частично выровнены на `destructive`, но старые handoff/diff notes все еще могут упоминать прежний drift `danger` vs `destructive`.
- Primitive layer смешан между Base UI и legacy Radix wrappers.
- `employee detail` уже переведен в Vite/shared runtime и разрезан на `main.tsx + page.tsx + sections.tsx + helpers.ts`, но все еще тянет legacy visual patterns через собственный CSS и createElement-heavy sections.
- Новые React templates уже отделены от legacy `base.html`, но при page-level правках все еще надо проверять, что old styles/selectors не возвращаются через classic partials или one-off CSS.

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
- Превращать `/app/design-system` в оторванную showcase-страницу, которая не соответствует реальным shared компонентам.

## Связанные файлы

- `frontend/src/index.css`
- `frontend/src/components/ui/*`
