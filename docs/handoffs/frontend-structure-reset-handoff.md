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

## 2026-05-31 — employees list UI kit alignment

### Changed

- `/app/employees` начал приводиться к текущему shadcn/Base UI baseline.
- Удалена ложная кнопка `Классическая`, которая вела на legacy `/employees` и больше не была полезным fallback action.
- Верхний переключатель `Сотрудники/Кандидаты` переведен на shared `Button`.
- Карточки сотрудников переведены на `Card`, metadata chips — на `Badge`.
- Loading/error/empty states переведены на `Skeleton`, `Alert`, `Empty`.
- Снят самый заметный hover radius morph на карточках и list rows.

### Screens

- `/app/employees`
- `/app/employees` после открытия create form
- `/app/employees` после переключения на candidates

### Shared UI API

- Используются существующие primitives из `frontend/src/components/ui/*`.
- Новые компоненты не добавлялись.
- Для link-actions используется `buttonVariants`, потому что текущий Base UI `Button` не должен получать старый `asChild` API.

### Docs Updated

- `docs/handoffs/frontend-structure-reset-handoff.md`

### Checks

- `frontend`: `npm run build`
- Headless browser smoke через Playwright + login `admin/admin123`
- Проверено:
  - legacy `/employees` CTA отсутствует
  - list render не пустой
  - create form открывается
  - переключение на candidates работает
  - console errors/warnings не пойманы

### Known Issues

- `SinglePicker` пока остается custom Popover-picker, а не полноценный shared Select/Combobox pattern.
- Table mode все еще не использует shared `Table`; это следующий логичный cleanup для `/app/employees`.
- Card density визуально нормальная, но employee detail page все еще живет в своем legacy CSS языке.

### Open Questions

- Нужно ли сделать отдельный documented pattern для compact operator list cards в `/app/design-system`.

### Next Agent Notes

- Не возвращать `Классическая`/legacy fallback CTA на React list pages без реального rollback смысла.
- Следующий шаг по employees: заменить table-mode на shared `Table` и вынести employee card/list row как documented pattern.

## 2026-05-31 — shell sidebar reset

### Changed

- `/app/*` shell sidebar перестроен из server-side hover/collapse набора в отдельный React mount `frontend/src/shell-sidebar/*`.
- `app/templates/react_base.html` больше не содержит старый HTML sidebar markup и inline nav-behavior script; теперь он только отдает root под React shell sidebar.
- `app/static/react_shell.css` очищен от старого React-shell/sidebar гибрида; overlay panel и rail теперь живут в одном CSS contract.
- Удален мертвый shared файл `frontend/src/components/ui/sidebar.tsx`, который больше не использовался и только дублировал ownership.

### Screens

- `/app/flows/workspace-v2`
- `/app/bulk-actions`
- косвенно весь `/app/*` shell, потому что sidebar общий

### Shared UI API

- Добавлен новый shell-only sidebar entrypoint `frontend/src/shell-sidebar/main.tsx`.
- Глобальный app shell больше не опирается на old `app-sidebar`/`app-shell-expanded` state contract.
- Новый контракт: rail фиксированный, panel overlay, open-state хранится в `sessionStorage` и переживает переходы между `/app/*`.

### Docs Updated

- `docs/features/ui-design-guidelines.md`

### Checks

- `frontend`: `npm run build`
- Headless browser smoke через Playwright + login `admin/admin123`
- Проверено:
  - rail не меняет ширину content area
  - overlay panel открывается поверх content
  - переход `/app/flows/workspace-v2 -> /app/bulk-actions` сохраняет open-state
  - active nav state обновляется на новом route
  - console errors/warnings не пойманы

### Known Issues

- Это еще не persistent SPA shell: между документами нет честной shared-element анимации, и пытаться её эмулировать через cross-document hacks не надо.
- Legacy `app/templates/base.html` пока не тронут; cleanup этого слоя надо делать отдельно после route audit, а не вперемешку с React shell.

### Open Questions

- Нужен ли следующий шаг с переносом shell sidebar visual contract на `/app/design-system` как отдельный documented pattern.

### Next Agent Notes

- Не возвращать hover-hotzone и любые auto-expand механики.
- Не переиспользовать старый `app-sidebar` CSS contract для новых React страниц.
- Если понадобится настоящая морфинг-анимация между разделами, это уже задача persistent client-side shell, а не CSS-патча поверх server navigation.

### Changed

- `frontend/src/design-system/page.tsx` переписан из короткой policy-страницы в live design-system baseline.
- Экран получил sticky top bar, jump-nav, manual light/dark toggle, foundations/primitives/patterns/review-rules sections и реальные interactive demos на базе shared UI.

### Screens

- `/app/design-system`

### Shared UI API

- Новый экран опирается на существующие primitives из `frontend/src/components/ui/*`, а не вводит второй UI-stack.
- Особенно зафиксированы как baseline: `Button`, `Input`, `Textarea`, `Select`, `Checkbox`, `Switch`, `Badge`, `Card`, `Table`, `Tabs`, `Breadcrumb`, `Dialog`, `Dropdown`, `Tooltip`, `Progress`, `Avatar`, `Skeleton`.

### Docs Updated

- `docs/features/ui-design-guidelines.md`
- `docs/project_state.md`
- `docs/backlog.md`

### Checks

- Пока запланирована только локальная build-проверка после завершения правок.

### Known Issues

- `/app/design-system` пока живет одной страницей; если content разрастется, его лучше делить на `foundations/primitives/patterns/review-rules`.
- Экран фиксирует текущие shared API, но сам по себе не выравнивает визуальный drift на `/app/employees`, `/app/settings`, `/app/bulk-actions`.

### Open Questions

- Нужно ли выводить часть design-system как отдельные подпути сейчас или сначала привести по нему 2-3 боевые страницы.

### Next Agent Notes

- Не плодить новый showcase-слой и не строить primitives “с нуля под красивый промпт”.
- Любое изменение shared UI API должно быть отражено и в `/app/design-system`, и в docs.

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
4. `bulk-actions` уже вынесен в `app/web/bulk_actions.py` + `app/web/bulk_action_routes.py`, `settings` — в `app/web/settings.py` + `app/web/settings_routes.py`, `scenario/surveys` — в `app/web/scenarios.py` + `app/web/scenario_routes.py`, включая classic editor и survey export.
5. `app/main.py` больше не точка, где живет operator route ownership: он сжат до composition-root слоя с startup, middleware, auth/session pages и `include_router(...)`.
6. Следующий backend-проход уже не про новый slice, а про parity/remove pass:
   - какие classic fallback pages реально еще нужны
   - какие form actions можно убрать без rollback gap
7. Мертвые classic list templates уже удалены: `scenarios.html`, `mass_actions.html`, `settings.html` больше не участвуют в runtime.
8. Classic employee POST redirects уже возвращают в React detail `/app/employees/{id}` с `flash_message/flash_type`; React template и page поддерживают top-level flash banner.
9. Safe classic scenario/survey redirects (`POST /flows`, `/surveys`, `/{id}/copy`, `/{id}/delete`) уже возвращают в React workspace с `scenario_id` и `flash_message/flash_type`; React workspace template/page тоже поддерживают top-level flash banner.
10. Direct classic employee page тоже уже снят: `GET /employees/{id}/edit` редиректит в `/app/employees/{id}`, `employee_edit.html` удален из runtime, а React detail больше не держит ссылку “Классическая карточка”.
11. Per-button notifications больше не classic-only: `scenario-workspace` получил `button_notifications` в payload/types/UI, а `/api/flows/workspace/steps/{id}` теперь синхронизирует `StepButtonNotification` без legacy form submit.
12. Default `GET /flows/{id}` и `GET /surveys/{id}` уже больше не ведут в classic editor: они редиректят в React workspace, а legacy editor доступен только через `?legacy=1`.
13. `POST /flows/{id}` и `POST /surveys/{id}` пока намеренно остаются classic editor redirects. Это не забытый хвост, а осознанный rollback seam: если оператор зашел через `?legacy=1`, то save/delete-attachment/export-error больше не выбрасывают его в React случайно. Следующий вопрос теперь уже не про redirect consistency, а только про remaining nested update parity и судьбу `scenario_edit.html`.
14. Был runtime regression в `frontend/src/scenario-workspace/page.tsx`: `payload` использовался до `useState`, из-за чего React-root не рендерился и на странице сценариев оставалась только статическая кнопка `Классический список`. Баг исправлен.
15. При этом общий `npm run build` больше не является надежной проверкой только для scenario workspace: сейчас он может падать из-за параллельной ветки `/app/design-system` и ее импортов. Если работа идет в двух потоках, это нужно учитывать явно.
14. После этого уже добивать remaining shared Button/Select/Panel API и локальные page wrappers.

## Employee Detail Visual Reset - 2026-05-31

### Changed

- `/app/employees/{id}` пересобран визуально на shared shadcn/Base primitives: `Card`, `Button`, `Field`, `Input`, `NativeSelect`, `Textarea`, `Badge`, `Alert`, `Empty`.
- Убран старый локальный слой `react-section` с hover-radius morphs, самодельными кнопками и перегруженной боковой колонкой.
- Экран разделен на профиль слева и операторские действия справа.
- Документы разведены на:
  - `Файлы HR`: `EmployeeFile.direction !== "inbound"`
  - `Документы сотрудника`: `EmployeeFile.direction === "inbound"`
  - `Ссылки HR`: текущие `EmployeeDocumentLink`, сейчас оффер
- Чекбокс `Сразу отправить в мессенджер` удален из upload flow; отправка осталась отдельной кнопкой у каждого файла через существующий `/api/employees/{id}/files/{file_id}/send`.
- Добавлен UI-блок целевых реквизитов адаптации: наставник из списка, задачи на ИС, обратная связь, середина/конец адаптации, должность руководителя.

### Screens

- `/app/employees/9`

### Shared UI API

- Новых shared components не добавлено.
- `employee-detail` теперь зависит от существующих `frontend/src/components/ui/*` primitives.

### Backend Contract Needed

- Сериализовать `EmployeeFile.category` или явный `source` в `/api/employees/{id}`, иначе frontend может надежно делить документы только по `direction`.
- Добавить список сотрудников/наставников для picker поля `Наставник`.
- Добавить сохраняемые поля: `adaptation_tasks_url`, `adaptation_feedback_url`, `adaptation_mid_date`, `adaptation_end_date`.
- Уточнить, является ли текущий `first_workday` тем самым полем `Первый день сотрудника`; frontend сейчас использует его.
- Добавить `is_manager` или роль руководителя и `manager_position`, чтобы показывать `Должность руководителя` только руководителям.
- Решить, заменяем ли текущие `manager_chat_id`/`mentor_*_chat_id` на relation к сотруднику или оставляем как технические Telegram id.

### Checks

- `frontend`: `npm run build`
- Headless Playwright smoke через Python `playwright`:
  - `/app/employees/9` открывается после login
  - React grid рендерится
  - горизонтального overflow нет
  - console errors нет
  - screenshot: `tmp_employee_detail_qa/employee-9-desktop-v2.png`

### Known Issues

- Новые реквизиты адаптации в UI намеренно disabled, пока нет API/model contract.
- Разделение файлов сейчас опирается только на `direction` (`inbound`/`outbound`), без категории документа.
- Боковая колонка sticky на desktop; на узком viewport складывается вниз, но mobile-polish не делался.

## Global Theme Toggle - 2026-05-31

### Changed

- Тема вынесена из локального `/app/design-system` hook в общий `frontend/src/lib/theme.ts`.
- `react_base.html` применяет `html.dark` до загрузки CSS на всех React `/app/*` страницах.
- Shell sidebar получил глобальную кнопку переключения темы в rail и panel footer.
- `/app/design-system` теперь использует тот же theme helper, а не собственную isolated реализацию.

### Screens

- `/app/design-system`
- `/app/employees`

### Checks

- `frontend`: `npm run build`
- Headless Playwright smoke:
  - `localStorage.theme = "dark"` сохраняется после перехода `/app/design-system -> /app/employees`
  - `document.documentElement.classList.contains("dark") === true` на employees
  - sidebar theme button рендерится
  - console errors нет

### Known Issues

- Тема глобальна для React shell pages. Classic templates вне `react_base.html` не являются целью этого pass.

## Employee Detail Field Polish - 2026-05-31

### Changed

- `/app/employees/{id}` больше не использует `NativeSelect` для основных полей: должность, статусы и сценарии переведены на Base `Select` composition.
- Date/date-time поля переведены на shared `DatePicker` / `DateTimePicker`, собранные из `Popover + Calendar + TimePicker`.
- Удален промежуточный блок `HR-документы`; upload файла перенесен в `Файлы HR`, добавление ссылки перенесено в `Ссылки HR`.
- `Ссылки HR` визуально готов к нескольким ссылкам, но backend сейчас сохраняет только одну offer-ссылку.
- Кнопка `Отправить в мессенджер` теперь рендерится у каждого файла; если Telegram-привязки нет, ошибку возвращает backend.
- Убран лишний status chip внутри блока `Профиль сотрудника`; статус остается в hero.
- Убран текст `Карточка сотрудника: профиль, адаптация, документы и операторские действия.`
- Shared `PopoverContent` очищен от legacy hover-radius morph.

### Shared UI API

- Добавлен `frontend/src/components/ui/date-picker.tsx`.
- Изменен `frontend/src/components/ui/popover.tsx`: удален hover-driven radius morph, оставлен стабильный shadcn-like popover surface.

### Checks

- `frontend`: `npm run build`
- Headless Playwright smoke `/app/employees/9`:
  - React root рендерится без console/page errors
  - `NativeSelect`/native date inputs на employee detail больше не используются
  - `HR-документы` промежуточный card отсутствует
  - horizontal overflow нет

### Known Issues

- Для нескольких HR-ссылок нужен backend API/model: сейчас existing `/document-links` endpoint фактически upsert одного оффера.

## Employee Detail Control Fix - 2026-05-31

### Changed

- `DatePicker` fixed: Radix `PopoverTrigger` больше не оборачивает Base `Button`; trigger теперь plain `button` с `buttonVariants`, поэтому календарь открывается стабильно.
- `TimePicker` заменен на `TimeSelect` внутри `date-picker.tsx`; native `input[type=time]` больше не используется на employee detail и не дает белый browser popup в dark mode.
- Employee detail checkboxes переведены с `Input type="checkbox"` на shared `Checkbox`.
- `/app/design-system` обновлен: primitives section теперь показывает `DatePicker`, `TimeSelect`, `DateTimePicker`.

### Checks

- `frontend`: `npm run build`
- Headless Playwright smoke:
  - `/app/employees/9` calendar popup opens
  - `input[type=time]`, `input[type=date]`, `input[type=datetime-local]` count is `0`
  - dark-mode time popup background uses tokenized popover color
  - shared checkbox slot is rendered
  - `/app/design-system` contains Date picker / Time select / Date time examples

### Known Issues

- `TimeSelect` currently uses 15-minute options. If HR needs arbitrary minute precision, extend the shared component deliberately instead of returning to native time input.

## Shadcn Token Contract - 2026-06-01

### Changed

- `frontend/src/index.css` aligned with the adapted shadcn color contract: Tailwind v4 `@theme inline`, OKLCH tokens, neutral light accent, dark `primary-foreground`, radius scale and semantic `success/warning/info`.
- `frontend/src/components/ui/button.tsx` destructive variant now uses `text-destructive-foreground` instead of hardcoded white.
- `frontend/src/components/ui/popover.tsx` migrated from Radix Popover to shadcn Base Popover (`@base-ui/react/popover`).
- `frontend/src/components/ui/date-picker.tsx` updated to Base UI `render` trigger composition instead of Radix `asChild`.
- `/app/design-system` token cards now show the OKLCH token contract and semantic status tokens.
- Added `docs/features/shadcn-component-contract.md` as the frontend source of truth for shadcn/Base UI usage.
- `docs/project_state.md` updated with the Base UI first and no-new-Radix operating model.

### Screens

- `/app/design-system`
- `/app/employees/{id}` indirectly via `DatePicker` / `Popover`

### Shared UI API

- `PopoverTrigger` is now Base UI compatible and expects `render` for custom triggers.
- New shared UI must not introduce Radix wrappers. Existing Radix wrappers are migration debt, not accepted baseline.

### Checks

- `frontend`: `npm run build`
- Headless Playwright smoke through a temporary runner outside the repo:
  - `/app/design-system` renders token section, semantic tokens and success sample
  - CSS vars resolve to OKLCH `--primary-foreground` and neutral `--accent`
  - `/app/employees/9` opens DatePicker popover
  - native date/time inputs remain absent
  - console/page errors absent

### Known Issues

- `frontend/src/components/ui/scroll-area.tsx` is still Radix-based and should be migrated in a separate pass.
- `frontend/src/components/ui/sonner.tsx` still imports `next-themes`; do not use it in production flows until it is adapted to the local Vite theme helper.
- Older pages still contain raw red/amber Tailwind status classes; replace during page-specific passes.

## Employee Detail Layout Cleanup - 2026-06-01

### Changed

- `/app/employees/{id}` cleaned up after visual review: removed block descriptions, field descriptions and backend-explanation text from the rendered employee card.
- File row actions changed to icon-only download/send buttons with `aria-label` and `title`.
- Employee detail layout restructured into visible groups: `Профиль`, `Работа`, `Адаптация`, `Заметки`, `Сценарии`, `Документы`, `Очередь`, `Опасная зона`.
- Right operations column is no longer sticky, avoiding long-column scroll/overlap problems.
- Document rows tightened: fixed action column, no wrapping action labels, no horizontal overflow.
- Hero copy reduced to name and status pills only.

### Screens

- `/app/employees/9`

### Shared UI API

- No new shared primitives. Existing `Button`, `DatePicker`, `Select`, `Checkbox`, `Card`, `Empty` were reused.

### Checks

- `frontend`: `npm run build`
- Headless Playwright smoke `/app/employees/9`:
  - page loads with no console/page errors
  - document download/send actions have empty visible text and accessible labels
  - no card/field/empty descriptions remain in employee detail DOM
  - semantic section labels render in the expected order
  - no horizontal overflow and no visible card/section overlaps at desktop viewport
  - DatePicker popover opens through real Playwright click

### Known Issues

- Planned adaptation fields are still disabled visual placeholders until backend contract/API exists.

## Employee Detail Kit Alignment - 2026-06-01

### Changed

- Employee hero status pills now use shared `Badge` instead of local `react-overview-pill` spans.
- Employee detail cards explicitly use `shadow-none ring-0`; the page now follows the no-shadow MVP baseline.
- Scheduled scenario row actions now match document rows: icon-only buttons with accessible labels.
- `/app/design-system` now documents the employee detail building blocks: section label, status badges and document row pattern.

### Screens

- `/app/employees/9`
- `/app/design-system#patterns`

### Shared UI API

- No new shared component file was introduced. The documented pattern still composes existing `Card`, `Badge`, `Button` and semantic tokens.

### Checks

- `frontend`: `npm run build`
- Headless Playwright light/dark smoke:
  - `/app/employees/9` renders in light and dark with expected `html.dark` state
  - OKLCH background/foreground tokens resolve in both themes
  - cards report `box-shadow: none`
  - document action visible text is empty, `aria-label` remains present
  - no horizontal overflow
  - no card/field/empty descriptions on employee detail
  - DatePicker popover opens in both themes
  - `/app/design-system#patterns` includes the new detail building block and document row pattern

### Known Issues

- Base `Popover` still carries upstream `shadow-md` in the shared component class, but global CSS neutralizes shadows. If we want literal class-level purity, clean it in a separate shared component pass.

## Employees List Kit Alignment - 2026-06-01

### Changed

- `/app/employees` filters now use Base UI `Select` composition instead of a custom Popover picker; nested button DOM is gone and filter menus align to their triggers.
- Removed page usage of shared `ScrollArea` because that wrapper is still Radix-based migration debt.
- Removed inline grid layout styles from employees list and replaced them with classes.
- Replaced legacy `var(--color-*)` aliases in employees list with semantic classes where touched.
- Main list card and employee cards now use `shadow-none ring-0` and tokenized hover via `hover:bg-accent/60`.
- Added `aria-label` to icon-only view toggles and card/chat actions.
- `/app/design-system#patterns` now includes `List page item` as the employees list baseline pattern.

### Screens

- `/app/employees`
- `/app/design-system#patterns`

### Shared UI API

- No new shared component file. Existing `Card`, `Badge`, `Button`, `Select`, `Input`, `Empty`, `Skeleton` were reused.

### Checks

- `frontend`: `npm run build`
- Headless Playwright smoke `/app/employees`:
  - light and dark render without console/page errors
  - no nested `button button`
  - no horizontal overflow
  - top card computed `box-shadow: none`
  - filters open Base Select menus aligned to the trigger
  - cards/table toggle works
  - icon-only actions expose `aria-label`
  - `/app/design-system#patterns` includes `List page item`

### Known Issues

- `ScrollArea` remains Radix-based globally, but `/app/employees` no longer consumes it.

## Scenario Workspace Kit Baseline - 2026-06-01

### Changed

- `/app/design-system#patterns` now includes `Workspace builder` as the baseline for three-column operator workspaces: navigation column, canvas column, detail editor column.
- `/app/flows/workspace-v2` and `/app/surveys/workspace` started moving to that baseline.
- Removed visible `Классический список` and `Legacy editor` actions from the operator workspace UI, including the React error fallback; the backend legacy seam can still exist, but it should not be the primary visual surface.
- Scenario/survey list column now uses shared `Card`, `Badge`, `Button`, `Input`, and `Checkbox` primitives instead of custom buttons/raw checkbox markup.
- Workspace canvas cards now use tokenized `Card`/`Badge` treatment and no hover radius morph.
- Scenario picker controls in the detail pane now use Base `Select` through `SingleSelectPicker`; empty values display real labels instead of implementation tokens.
- Replaced shared `frontend/src/components/ui/scroll-area.tsx` with a Base UI `ScrollArea` wrapper and used it in scenario workspace scroll regions.
- Scenario workspace container is now vertically centered and constrained to `94vh` / `100vh - 32px` instead of filling an asymmetric `calc(100vh - 30px)` box.
- Scenario workspace outer operator cards now explicitly match the employees dense-card radius baseline: `rounded-lg`, `border-border`, `shadow-none`, `ring-0`.
- Emoji insertion moved into shared `EmojiPickerPopover`: Base `Popover` + shared `Button`, lazy `emoji-picker-react`, theme from `frontend/src/lib/theme.ts`, public API limited to `onEmojiSelect(emoji)`.
- `frontend/vite.config.ts` now sets `base: "/static/workspace_v2/"`; without this, lazy chunks loaded from `/assets/...` and 404ed outside the Vite dev server.
- Shared `Button` now forwards refs; Base UI `render={<Button />}` triggers need that ref for Popover/Dialog positioning.
- Replaced remaining `asChild` usage in this workspace path with Base UI `render` composition where touched.

### Screens

- `/app/design-system#patterns`
- `/app/flows/workspace-v2`
- `/app/surveys/workspace`

### Shared UI API

- No new primitive files were added.
- Existing primitives reused: `Card`, `Badge`, `Button`, `Input`, `Textarea`, `Select`, `Checkbox`, `Popover`, `ScrollArea`, `Separator`, `EmojiPickerPopover`.
- New rule for this area: if a scenario workspace UI pattern is missing, add it to `/app/design-system` first, then apply it to the live page.

### Checks

- `frontend`: `npm run build`
- Headless Playwright smoke:
  - `/app/flows/workspace-v2` renders without console/page errors
  - `/app/surveys/workspace` renders without console/page errors
  - no visible `Классический список`
  - no visible `Legacy editor`
  - no nested `button button`
  - no native `select`
  - no horizontal overflow
  - empty select values no longer show `__empty__`
  - `/app/design-system#patterns` contains `Workspace builder`

### Known Issues

- `WorkspaceStepDetailPane` is partially cleaned, but notification sub-blocks still use `space-y-*`; convert them to `grid/flex gap-*` in a later cleanup pass if strict shadcn lint is added.
- Base `Checkbox` renders internal input nodes, so DOM checks for `input[type=checkbox]` are not a useful proxy for raw checkbox debt anymore; audit source code instead.
- The three-column workspace is desktop-first only in this pass. Mobile layout was not targeted.
