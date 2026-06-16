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

## 2026-06-10 — shared document library for bot menu

### Changed

- Добавлен новый React surface `/app/documents` с отдельным Vite entry `frontend/src/documents/main.tsx`.
- В sidebar появился отдельный системный пункт `Документы`.
- Shared bot materials больше не привязываются к menu buttons как raw file path/url:
  - введена отдельная сущность `DocumentLibraryItem`;
  - новый backend slice вынесен в `app/web/documents.py` + `app/web/document_routes.py`;
  - у `BotMenuButton` появился `action_type=send_document` и ссылка `document_item_id`.
- `/app/bot-menu` теперь получает `document_options` из settings workspace payload и умеет привязывать кнопку к shared document item.
- Runtime бота в `app/messaging/service.py` умеет:
  - отправлять shared link как текст с URL;
  - отправлять shared file как Telegram document.

### Screens

- `/app/documents`
- `/app/bot-menu`

### Shared UI/API contract

- Shared documents живут отдельно от employee files. Не использовать `employee_files` как общую библиотеку.
- Bot menu не должен хранить raw `stored_path` или `external_url` внутри кнопки.
- Базовый contract сейчас такой:
  - `DocumentLibraryItem.item_kind = file | link`
  - `BotMenuButton.action_type = send_document`
  - menu navigation для каталогов документов продолжает строиться через уже существующие `open_set` + `menu sets`.
- Для ускорения ручной настройки добавлен `menu-scaffold` helper на `/app/documents`: он создает root menu set и category child sets из active documents.
- Scaffold теперь поддерживает controlled rebuild:
  - `create` падает, если generated root с тем же названием уже есть;
  - `rebuild` пересобирает только ветку с тем же `system_tag`, не трогая ручные `menu sets`.

### Checks

- `.\.venv\Scripts\python.exe -m compileall app tests`
- `.\.venv\Scripts\python.exe -m unittest tests.test_employee_api_smoke -v`
- `npm run build`
- Browser smoke `/app/documents` at 1280 px in light and dark themes:
  - no horizontal overflow or console errors;
  - shared card/input/button radii and semantic theme colors verified;
  - delete confirmation verified without completing deletion.

### Known Issues

- Текущая страница документов еще не решает product-задачу категоризации внутри самого bot menu. Есть shared library и `send_document`, но структура submenu по категориям должна собираться самими `menu sets`, а не магическим “списком документов” вне menu architecture.
- `/app/documents` приведена к shared UI contract: external/download actions используют `Button`, delete использует `ConfirmAction`, file picker больше не показывает англоязычный browser-native control.

### Next Agent Notes

- Не встраивать библиотеку документов обратно в `/app/settings`.
- Не дублировать document payload внутри `bot-menu`.
- Если дальше будет много документов, следующий шаг — не pagination-first, а нормальная menu taxonomy: отдельные `menu sets` под категории/разделы и кнопки `send_document` внутри них.
- Если scaffold начнет плодить дубли, следующий шаг — не усложнять runtime, а добавить controlled replace/update policy для generated document menu trees.
- Этот controlled replace/update policy уже реализован через `BotMenuSet.system_tag`; следующий шаг нужен только если появится требование partial update вместо full rebuild ветки.

## 2026-06-09 — survey flow simplification

### Changed

- `/app/surveys/workspace` больше не показывает scenario-only step controls:
  - нет выбора типа ответа;
  - нет `Переход к сценарию`;
  - нет `Сохранить ответ`;
  - нет настройки `Режим отправки`;
  - нет step-level notifications.
- На уровне root-toolbar у опросов также убрана кнопка `Настройки`: audience/constraints для survey не редактируются из этого экрана, потому что опросы планируются как сущности для mass-launch flow, а не как самостоятельные trigger-bound сценарии.
- Для survey-step `Название` и `Текст` схлопнуты в одно поле `Вопрос`; при сохранении backend синхронизирует `title/text/default_text`.
- `Варианты ответа` теперь отдельный textarea-блок: каждая строка — отдельный готовый вариант ответа. Это не branching, а просто option buttons для текстового вопроса.
- Runtime survey-flow изменен: если у текстового survey-question есть `button_options`, бот показывает их как кнопки, но шаг по-прежнему считается текстовым question-flow, а выбранный вариант сохраняется как обычный answer value.
- Excel export для `/surveys/{id}/export` переделан с широкой матрицы на плоский формат строк:
  - `Пользователь ФИО`
  - `Вопрос`
  - `Ответ`

### Screens

- `/app/surveys/workspace`
- `/surveys/{id}/export`

### Shared UI/API contract

- Survey-step больше не должен использовать scenario-only payload semantics даже если общая React page остается общей.
- `button_options` в survey означают answer variants, а не branching.
- Workspace API при сохранении survey-step игнорирует и очищает:
  - `send_mode`
  - `send_time`
  - `target_field`
  - `launch_scenario_key`
  - `send_employee_card`
  - step/button notifications

### Checks

- `backend`: `python -m compileall app tests`
- `backend`: `python -m unittest tests.test_scenario_engine_smoke tests.test_messaging_identity tests.test_employee_api_smoke tests.test_scenario_engine_branching -v`
- `frontend`: `npm run build`
- Добавлены проверки на:
  - survey-step normalization через `/api/flows/workspace/steps/{id}`
  - runtime acceptance survey option buttons without branching response type
  - flattened survey Excel export content

### Known Issues

- Survey и scenario по-прежнему живут в одном React bundle и одном route module, поэтому часть page-level plumbing остается общей. Контракт уже разошелся, но кодовая поверхность еще не полностью разделена.
- Legacy `scenario_edit.html` еще не переучен на новый survey-specific UX, но default survey ownership уже у React workspace.

## 2026-06-09 — scenario workspace step notification rules

### Changed

- Блок `Уведомление для шага` в `scenario-workspace` переведен с одного плоского набора полей на список rules с add/edit/delete через modal workflow, как уже сделано для `Уведомления по кнопкам`.
- Backend получил отдельную сущность `StepSendNotification`; React workspace теперь сохраняет `step_send_notifications[]` через `/api/flows/workspace/steps/{step_id}`.
- Runtime `send_step(...)` отправляет все step-level notification rules по `rule_index`, а не только один legacy notification payload.
- Copy/delete scenario flows и workspace serialization тоже знают про `StepSendNotification`, поэтому rules не теряются при копировании сценария и удалении subtree.
- Legacy `notify_on_send_*` поля не удалены совсем: они продолжают отражать первый rule как compatibility seam для fallback/старых payloads.

### Screens

- `/app/flows/workspace-v2`
- `/app/surveys/workspace`

### Shared UI/API contract

- `WorkspaceStep` теперь содержит `step_send_notifications[]`.
- Step notification rule хранит:
  - `rule_index`
  - `message_text`
  - `recipient_ids`
  - `recipient_scope`
- Explicit recipients продолжают храниться как `employee:{id}` tokens и резолвятся в chat id только в runtime, не в React form state.

### Checks

- `backend`: `python -m compileall app tests`
- `backend`: `python -m unittest tests.test_scenario_engine_smoke tests.test_messaging_identity tests.test_employee_api_smoke tests.test_scenario_engine_branching -v`
- `frontend`: `npm run build`
- Добавлены smoke/assertions на:
  - persistence `step_send_notifications` через workspace API
  - повторное сохранение уже существующих rules без потери или дублирования
  - runtime dispatch всех step-level notification rules

### Known Issues

- `scenario_edit.html` все еще остается fallback surface; step notifications там пока не становятся полноценным multi-rule editor.
- Пока жив classic fallback, legacy `notify_on_send_*` bridge лучше не удалять резко, иначе можно сломать старые form flows и rollback seam.
- После backend-изменений процесс `uvicorn` обязательно нужно перезапускать. Старый процесс принимает новый frontend payload, сохраняет только legacy first-rule поля и возвращает пустой `step_send_notifications[]`, из-за чего UI выглядит так, будто правила не сохраняются.

## 2026-06-09 — settings and bot menu visual QA

### Changed

- `/app/settings` больше не падает пустым React-root: восстановлен импорт shared `Button`.
- Settings shortcut на `/app/bot-menu` приведен к текущему page/card baseline без лишнего описательного текста.
- Заголовок `HR notifications` заменен на `HR-настройки`, success message сохранения тоже русифицирован.
- Нативные `window.confirm` для удаления на `/app/settings` и `/app/bot-menu` заменены на shared `ConfirmAction` поверх shadcn/Base `AlertDialog`.
- Template cache для settings поднят до `settings.js?v=11`, для bot-menu до `bot-menu.js?v=2`.

### Screens

- `/app/settings`
- `/app/bot-menu`

### Shared UI/API contract

- Добавлен shared wrapper `ConfirmAction` в `frontend/src/components/ui/confirm-action.tsx`.
- Используются существующие `Card`, `Field`, `Input`, `Textarea`, `Select`, `Checkbox`, `Button`, `Alert`, `AlertDialog`.
- Bot-menu по-прежнему живет на текущем `/api/settings/workspace` и `/api/settings/menu-*` contract.

### Checks

- `frontend`: `npm run build`
- Browser smoke `/app/settings`: root rendered, `settings.js?v=11`, horizontal overflow `0`.
- Browser interaction `/app/settings`: opening first `Select` kept main container width stable at `1178.6667px`.
- Browser smoke `/app/bot-menu`: root rendered, horizontal overflow `0`, main card radius `20px`, controls/selects `14px`.
- Browser interaction `/app/bot-menu`: opening first `Select` kept main container width stable at `1178.6667px`.
- Dark theme toggled through sidebar and persisted from `/app/settings` to `/app/bot-menu`; card/input/select colors resolved from semantic tokens.
- `npx shadcn@latest info --json` confirmed `base-nova`, Vite, Tailwind v4, Base UI.
- `npx shadcn@latest docs alert-dialog` checked; local usage follows Base `render={<Button />}` trigger composition.
- Browser dialog smoke `/app/bot-menu`: delete set opens `AlertDialog`, radius `20px`, destructive action only inside dialog, cancel closes without mutation.
- Browser dialog smoke `/app/settings`: delete account opens `AlertDialog`, radius `20px`, destructive action only inside dialog, cancel closes without mutation.

### Known Issues

- Browser console buffer can still show old `settings.js?v=9` `Button is not defined` errors from before reload; current loaded settings script is `v=11`.
- `settings` and `bot-menu` still duplicate workspace normalization/helpers. Keep this as cleanup debt, not a reason to merge pages back.

## 2026-06-09 — design system sync after settings/bot/sidebar changes

### Changed

- `/app/design-system#patterns` updated with live patterns for `Bot menu editor`, `Shell sidebar`, and `Confirmation dialog`.
- `Settings form` example now matches current settings boundary: `HR-настройки`, no `HR notifications`, no `Главный набор меню`.
- `Detail page building blocks` no longer shows section-label or adaptation-field callout; support card example uses real current fields.
- Button primitives no longer present delete as a naked destructive button; destructive delete is shown through `ConfirmAction`.
- Template cache for design system bumped to `design-system.js?v=24`; shared `app.css` cache bumped to `app.css?v=44`.

### Screens

- `/app/design-system#patterns`

### Shared UI/API contract

- No new shared primitives changed in this pass.
- Existing `ConfirmAction`, `AlertDialog`, `Card`, `Field`, `Select`, `Checkbox`, `Button`, `Alert`, `ScrollArea`, and semantic tokens were documented as page patterns.

### Checks

- `frontend`: `npm run build`
- Browser smoke `/app/design-system#patterns`: `design-system.js?v=24`, `app.css?v=44`, new pattern blocks present, old `HR notifications`/`Главный набор меню`/adaptation callout absent, horizontal overflow `0`, console errors/warnings empty.
- Browser interaction `/app/design-system#patterns`: `Confirm delete` opens `AlertDialog`, radius `20px`, destructive action tokenized, cancel closes without mutation.

## 2026-06-09 — employee detail adaptation callout cleanup

### Changed

- `/app/employees/{id}`: removed the visible readonly callout about excluded adaptation fields from the `Сопровождение` card.
- Template cache for employee detail bumped to `employee-detail.js?v=13`.

### Screens

- `/app/employees/11`

### Shared UI/API contract

- No shared UI primitives or backend contracts changed.
- Unsupported adaptation fields were not reintroduced as fake UI.

### Checks

- `frontend`: `npm run build`
- Browser smoke `/app/employees/11`: root rendered, `employee-detail.js?v=13`, removed text absent, `Сопровождение` card contains only current real fields plus consent, horizontal overflow `0`, console errors/warnings empty.

## 2026-06-09 — dashboard sidebar icon

### Changed

- Dashboard brand/sidebar icon changed from `Bot` to `LayoutDashboard`.
- `Меню бота` keeps the `Bot` icon, so bot-specific navigation is no longer visually conflated with the dashboard entry.
- Template cache for shell sidebar bumped to `shell-sidebar.js?v=5`.

### Screens

- `/app/dashboard`

### Shared UI/API contract

- No shared UI primitives changed.
- Existing lucide icon import only.

### Checks

- `frontend`: `npm run build`
- Browser smoke `/app/dashboard`: `shell-sidebar.js?v=5`, active dashboard brand rendered as `lucide-layout-dashboard`, bot-menu icon still separate, horizontal overflow `0`, console errors/warnings empty.

## 2026-06-09 — bot menu extracted from settings

### Changed

- Редактор menu sets и audience-targeting вынесен из `/app/settings` в отдельный React surface `/app/bot-menu`.
- В `settings` остались только HR/system settings и admin accounts; shortcut-card и `default_menu_set` selector тоже убраны, чтобы страница вообще не выглядела частичным владельцем bot-menu.
- Sidebar получил отдельный системный пункт `Меню бота`.
- Добавлен новый template `app/templates/react_bot_menu.html` и отдельный Vite entry `frontend/src/bot-menu/main.tsx`.
- Audience contract упрощен: stage-targeting больше не участвует в menu-set matching. Для bot menu остаются `employee_scope`, `role_scope` и `target_employee_ids` с multiselect UI.
- Один и тот же сотрудник/кандидат больше не должен попадать в два разных explicit menu sets: UI скрывает уже занятые записи в других наборах, а backend API возвращает `409`, если старый/stale клиент все же попытается сохранить конфликт.

### Screens

- `/app/settings`
- `/app/bot-menu`

### Shared UI/API contract

- Новый экран пока переиспользует тот же `/api/settings/workspace` и `/api/settings/menu-*` contract.
- Это pragmatic step, а не финальная архитектура: часть helpers/type-normalization сейчас дублируется между `frontend/src/settings/page.tsx` и `frontend/src/bot-menu/page.tsx`.

### Checks

- `frontend`: `npm run build`
- backend/tests: `.\.venv\Scripts\python.exe -m unittest tests.test_employee_api_smoke -v`
- `.\.venv\Scripts\python.exe -m compileall app tests`
- Добавлен smoke на mount route `/app/bot-menu`

### Known Issues

- Если локальный backend-процесс на `127.0.0.1:8000` не перезапущен, браузер может продолжать отдавать старый `/api/settings/workspace` без audience fields и старый route table без `/app/bot-menu`.
- Текущий split решает product boundary, но еще не решает code duplication между `settings` и `bot-menu`.

### Next Agent Notes

- Не возвращать menu-set редактор обратно в `/app/settings`: это снова смешает системные настройки с bot UX rules.
- Следующий technical cleanup по этому модулю — не новая страница, а вынос shared helpers/types между `settings` и `bot-menu`.

## 2026-06-08 — menu audience targeting

### Changed

- `BotMenuSet` перестал быть просто списком кнопок: появились `role_scope`, `employee_scope`, `target_employee_id`, `target_employee_stages`, `target_candidate_stages`.
- `/app/settings` и `/api/settings*` теперь позволяют настраивать audience для каждого menu set.
- Bot runtime больше не открывает и не выбирает наборы вслепую:
  - `current_menu_set` сохраняется только пока набор совместим с сотрудником;
  - если набор не подходит, runtime выбирает следующий matching set;
  - `open_set` блокируется для несовместимого target menu.

### Screens

- `/app/settings`
- Telegram bot menu runtime

### Shared UI/API contract

- Settings workspace теперь отдает:
  - `menu_role_scope_labels`
  - `menu_employee_scope_labels`
  - `employee_options`
  - `employee_stage_options`
  - `candidate_stage_options`
- `menu_sets[]` теперь содержит:
  - `role_scope`
  - `employee_scope`
  - `target_employee_id`
  - `target_employee_stages`
  - `target_candidate_stages`

### Checks

- `.\.venv\Scripts\python.exe -m compileall app tests`
- `.\.venv\Scripts\python.exe -m unittest tests.test_scenario_engine_smoke tests.test_messaging_identity tests.test_employee_api_smoke tests.test_scenario_engine_branching -v`
- `npm run build`
- Smoke добавлен на:
  - persistence audience fields через settings API
  - runtime resolution matching candidate menu
  - guard на `open_set` для incompatible menu

### Known Issues

- Это пока menu-audience layer, а не полноценная access-control model для всей mini app и всех bot actions.
- Если дальше появятся candidate-only или employee-only mini app sections, их надо опирать на тот же backend contract, а не просто прятать кнопки во frontend.

### Next Agent Notes

- Не плодить второй параллельный access-layer.
- Если нужен доступ к mini app или новым bot actions, завязывать его на те же audience rules или на явный следующий уровень persona/access model.

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
16. Employee detail получил первый честный API/UI cleanup slice: добавлен `DELETE /api/employees/{id}/files/{file_id}`, payload employee files теперь отдает `delete_url`, а React detail умеет удалять файлы и document links по конкретной строке вместо глобального “удали первую ссылку”.
17. Fake `PlannedField`-заглушки в employee detail убраны: новая карточка больше не показывает поля сопровождения, для которых нет data contract и сохранения. Если эти поля вернутся, их нужно заводить как полноценный DB/API/UI slice, а не как placeholder markup.
18. `manual_launch_history` больше не теряется между backend и frontend: employee detail теперь показывает отдельный блок истории ручных запусков, а smoke-тест закрепляет presence этого массива в `/api/employees/{id}`.
19. Bulk actions API чуть выровнен по смыслу: frontend удаляет запланированные опросы через `/api/bulk-actions/surveys/{id}`, а backend держит отдельный survey delete alias вместо скрытого использования `.../scenarios/{id}` для обоих видов сущностей.
20. Поверх behavioral smoke добавлен route-contract smoke на frontend fetch layer: тест явно проверяет существование текущих `/login`, `/api/employees*`, `/api/bulk-actions*`, `/api/settings*`, `/api/accounts*` и `/api/flows/workspace*` routes, чтобы не ловить позже регрессии вида “кнопка жива, route исчез”.
21. После этого уже добивать remaining shared Button/Select/Panel API и локальные page wrappers.

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

## Settings And Bulk Actions UI Baseline - 2026-06-04

### Changed

- `/app/design-system#patterns` now documents `Settings form` and `Bulk action console`.
- Shared `DateTimePicker` now opens its time `SelectContent` with `alignItemWithTrigger={false}` to match employees filters.
- Global autofill styles in `frontend/src/index.css` keep autofilled inputs tokenized instead of browser-white.
- `/app/settings` now uses shared `Card`, `Field`, `Input`, `Textarea`, `Select`, `Checkbox`, `Button`, and `Alert`.
- `/app/bulk-actions` now uses shared `Card`, `Field`, `Select`, `Checkbox`, `DateTimePicker`, `Badge`, `Button`, and `Alert`.
- Removed visible classic/fallback entry buttons from settings and bulk React entrypoints.
- Removed bulk page-local template CSS that duplicated card/grid/form styling.
- Bumped settings/design-system script query versions after the final layout tweak so the browser does not keep stale bundles.
- Tightened the settings/bulk pass against the shadcn workflow gate: notification/stage checkbox groups now use `FieldSet`/`FieldLegend`/`FieldGroup`, bulk stage filters use shared `ScrollArea`, and empty history blocks use shared `Empty`.
- Bumped settings, bulk-actions, and design-system script query versions after the FieldSet/ScrollArea/Empty cleanup.
- Removed stale `React admin` labels from settings and bulk headers.
- Radius baseline verified for settings/bulk: outer cards and headers resolve to 20px, inner fieldsets and select triggers resolve to 14px.

### Screens

- `/app/design-system#patterns`
- `/app/settings`
- `/app/bulk-actions`

### Shared UI API

- No new primitive files were added.
- Existing primitives reused: `Card`, `Field`, `Input`, `Textarea`, `Select`, `Checkbox`, `DateTimePicker`, `Badge`, `Button`, `Alert`.
- Shared `DateTimePicker` behavior changed only in dropdown alignment; public props are unchanged.

### Checks

- `frontend`: `npm run build`
- In-app browser smoke:
  - `/app/settings` renders without console errors in light and dark theme
  - `/app/bulk-actions` renders without console errors in light and dark theme
  - `/app/design-system#patterns` renders with new settings/bulk patterns
  - no visible classic/fallback entrypoints
  - no native `select`
  - no native `input[type=datetime-local]`, `input[type=date]`, or `input[type=time]`
  - no horizontal overflow
  - Base `Select` popovers open and use dark tokens after toggling dark mode through `/app/design-system`
  - `DateTimePicker` calendar and time select open and use dark tokens on `/app/bulk-actions`
  - visible controls are not clipped below 24px; Base hidden checkbox inputs are ignored as implementation internals
  - latest smoke after FieldSet/ScrollArea/Empty cleanup: `/app/settings` and `/app/bulk-actions` load `settings.js?v=7` and `bulk-actions.js?v=7`, have no native select/date controls, no legacy text, no horizontal overflow, and dark select popovers use dark tokens
  - latest radius/header audit: `/app/settings` header text is `Настройки`, `/app/bulk-actions` header text is `Массовые действия`, both pages have no visible `React admin`, no horizontal overflow, card/header radius 20px, fieldset/select radius 14px

### Known Issues

- Real browser profile autofill is hard to trigger deterministically in browser automation; CSS rule presence was verified, but manual profile-autofill should still be checked with saved Chrome data.
- In-app screenshot capture worked earlier with viewport clips, but timed out during the final retry after this cleanup. DOM, interaction, theme, and layout metrics completed.

## Login React UI Baseline - 2026-06-04

### Changed

- `/login` is now a standalone React/Vite entrypoint (`frontend/src/login/main.tsx` + `frontend/src/login/page.tsx`).
- `app/templates/login.html` is now only a pre-auth shell: theme bootstrap, `#react-login-root`, `app.css`, and `login.js`.
- The login form uses shared `Card`, `Field`, `Input`, `Button`, and `Alert` primitives.
- The form keeps native `POST /login` behavior; backend auth flow is unchanged.
- `/app/design-system#patterns` now includes an `Auth page` card and `Auth form` example.
- Added early theme bootstrap on `/login` using the shared `theme` localStorage key and `.dark` document class.
- Removed the temporary scoped `auth-*` CSS from `app/static/styles.css`; login no longer depends on the legacy stylesheet.
- Added Vite input `login` and generated `/static/workspace_v2/login.js`.
- Bumped design-system script query to `design-system.js?v=19`.

### Screens

- `/login`
- `/app/design-system#patterns`

### Shared UI API

- No React primitives changed.
- Existing primitives reused: `Card`, `Field`, `Input`, `Button`, `Alert`.

### Checks

- `frontend`: `npm run build`
- HTTP smoke:
  - `GET /login` returns status 200, `react-login-root`, `workspace_v2/app.css?v=39`, and `login.js?v=1`
  - `GET /login` does not include `auth-copy`, `auth-panel`, or `/static/styles.css`
  - `POST /login` with invalid credentials returns status 200, `react-login-root`, `login.js?v=1`, and `Неверный логин или пароль.`
- In-app browser visual/DOM smoke:
  - `/login` renders through `login.js?v=1`
  - visible text is `Вход`, `Логин`, `Пароль`, `Войти`
  - no visible `auth-copy` block
  - shared card/input/button are present
  - card radius resolves to 20px
  - input/button radius resolves to 14px
  - no horizontal overflow

### Known Issues

- Browser automation in this session could read the login page but could not type into fields because the in-app Browser virtual clipboard is unavailable. The tab stayed on `/login`; manual login is needed to restore the visible session.
- Dark-mode persistence is implemented through the same template bootstrap and `app.css` tokens as React admin pages, but could not be toggled live through browser automation because the Browser read-only evaluation scope blocked localStorage writes and DOM mutation.

## Employee Detail Label Cleanup - 2026-06-06

### Changed

- Removed duplicated `employee-section-label` captions from the employee/candidate detail page.
- Card titles are now the only visible block labels on the page.
- Removed the unused `.employee-section-label` CSS rules.
- Added explicit spacing for employee detail document tools so upload/link buttons do not touch empty states or document lists.
- Split form action-row wrapping from compact document-row actions.
- Bumped shared React CSS query to `app.css?v=40`.
- Bumped employee detail script query to `employee-detail.js?v=10`.

### Screens

- `/app/employees/{employee_id}`

### Shared UI API

- No shared UI primitives changed.

### Checks

- `frontend`: `npm run build`
- Static grep: no `employee-section-label` remains in employee detail source.
- Static grep: no `employee-section-label` remains in built `employee-detail.js`.
- `git diff --check` passes; only existing CRLF warnings are reported.

### Known Issues

- Browser visual smoke requires an authenticated admin session; the current browser tab is still on `/login`.

## Bulk Actions Button Semantics - 2026-06-07

### Changed

- `/app/bulk-actions` no longer uses destructive red buttons for immediate send/launch actions.
- Immediate `Сейчас` actions use the default primary button.
- `Запланировать` actions use the secondary button.
- Stage checkbox groups now render the label above a bordered container instead of using visible `legend` text on the fieldset border.
- `/app/design-system#patterns` `Bulk action console` now documents the same button semantics.
- Bumped script queries to `bulk-actions.js?v=9` and `design-system.js?v=21`.

### Screens

- `/app/bulk-actions`
- `/app/design-system#patterns`

### Shared UI API

- No shared UI primitives changed.
- Destructive button semantics remain reserved for delete/irreversible risk and error states.

### Checks

- `frontend`: `npm run build`
- Static grep: no `variant="destructive"` remains in `frontend/src/bulk-actions/page.tsx`.
- Static grep: no visible `FieldLegend` remains in `frontend/src/bulk-actions/page.tsx`.
- Template grep: `/app/bulk-actions` loads `bulk-actions.js?v=9`; design system loads `design-system.js?v=21`.

## Admin Page Width And Radius Baseline - 2026-06-08

### Changed

- Added shared page layout tokens: `--admin-page-max-width: 1820px`, `--admin-page-gutter`, and `--admin-page-radius`.
- Added reusable React classes: `.admin-page-shell`, `.admin-page-stack`, and `.admin-page-surface`.
- Unified regular admin page caps across dashboard, employees, employee detail, settings, bulk actions, and design system.
- Replaced dashboard/settings/bulk/design-system/employees page-local max-width wrappers with shared classes.
- Standardized main page header/surface radius through `.admin-page-surface`.
- Left scenario workspace width separate because it is a viewport-height workspace canvas, not a regular page stack.
- Bumped cache queries for `react_shell.css`, `app.css`, dashboard, employees, employee detail, settings, bulk actions, and design system bundles.

### Screens

- `/app/dashboard`
- `/app/employees`
- `/app/employees/{employee_id}`
- `/app/settings`
- `/app/bulk-actions`
- `/app/design-system`

### Shared UI API

- No primitive component API changed.
- Added shared page layout CSS classes and tokens.

### Checks

- `frontend`: `npm run build`
- Static grep: no regular admin page keeps page-local `max-w-[1680px]`, `max-w-[1720px]`, `max-w-[1760px]`, `max-w-[1820px]`, or `max-w-[1960px]`.
- Static grep: only scenario workspace keeps its intentional `1760px` canvas cap.
- Static grep: compiled `app.css` contains `.admin-page-shell`, `.admin-page-stack`, and `.admin-page-surface`.
- `git diff --check` passes; only existing CRLF warnings are reported.

## Employee Detail Adaptation Contract - 2026-06-09

### Changed

- Employee detail no longer edits manager/mentor fields as raw Telegram ids.
- Added real relation fields in backend/model contract:
  - `manager_employee_id`
  - `mentor_adaptation_employee_id`
  - `mentor_ipr_employee_id`
  - `adaptation_tasks_url`
  - `adaptation_feedback_url`
  - `adaptation_midpoint`
  - `adaptation_end`
- React employee detail now renders manager and mentors as selects from employees with `employee_stage == "staff"`.
- `mid_probation` and `end_probation` scenario triggers now prefer explicit `adaptation_midpoint` / `adaptation_end` dates from the employee card instead of only deriving from `first_workday`.
- Runtime compatibility is preserved: when a related staff employee is selected, legacy `manager_telegram_id` / `mentor_*_telegram_id` fields are synced from that employee’s primary Telegram chat id for existing notification flows.

### Screens

- `/app/employees/{employee_id}`

### Shared UI API

- No shared primitive API changed.
- Employee detail consumes existing `SelectField`, `DatePicker`, `Input`, and card primitives.

### Checks

- `.\.venv\Scripts\python.exe -m compileall app tests`
- `.\.venv\Scripts\python.exe -m unittest tests.test_scenario_engine_smoke tests.test_messaging_identity tests.test_employee_api_smoke tests.test_scenario_engine_branching -v`
- `npm run build`
- `.\.venv\Scripts\python.exe -c "from app.main import app; assert app is not None"`
- `.\.venv\Scripts\python.exe -c "from app.bot_runner import main; assert main is not None"`

## Candidate To Adaptation Cutover - 2026-06-09

### Changed

- Employee detail now exposes an explicit HR action `Перевести в адаптацию` for candidates instead of assuming any auto-convert from bot-side offer acceptance.
- Added `POST /api/employees/{employee_id}/promote-to-adaptation`.
- Cutover rules are intentionally strict:
  - employee must still be in `candidate`
  - `first_workday` must already be filled in
  - transition clears `candidate_work_stage`
  - transition seeds `adaptation_midpoint` / `adaptation_end` from `first_workday` using workday-based probation math when explicit dates are missing
  - transition clears `current_menu_set_id`, so staff/adaptation audience can be recalculated instead of carrying a candidate menu set forward
- React employee detail disables the button until `first_workday` is filled, instead of letting HR hit a guaranteed backend validation error.

### Screens

- `/app/employees/{employee_id}`

### Product boundary

- This is **not** auto-promotion from a Telegram answer like “accepted offer”.
- That automation is still intentionally unresolved because it needs a separate lifecycle decision: `offer accepted` is not the same thing as `employee is ready for adaptation`.

### Checks

- `.\.venv\Scripts\python.exe -m unittest tests.test_scenario_engine_smoke tests.test_messaging_identity tests.test_employee_api_smoke tests.test_scenario_engine_branching -v`
- `npm run build`

## Scenario Workspace Notification Rules - 2026-06-09

### Changed

- Button notifications in React scenario workspace no longer assume one notification per button.
- Each button now has a list of notification rules with add/edit/delete actions.
- Rule editing moved into a modal flow instead of inline giant text blocks.
- Rule payload shape is now:
  - `button_notifications[]`
  - each item keeps `option_index`, `option_label`
  - each item contains `rules[]`
- `StepButtonNotification` got `rule_index`, so backend/runtime can persist and order several rules for the same button.
- Runtime behavior changed too: when a user presses a button, bot-side `handle_button_response` now sends **all** matching rules for that button in order, not just the first one.
- Explicit recipients from React workspace are no longer ambiguous raw ids:
  - picker stores them as `employee:{id}` tokens
  - runtime resolves those tokens to real Telegram chat ids
  - legacy raw chat ids still remain accepted for classic/fallback flows

### Important boundary

- Classic `scenario_edit.html` was not redesigned into the new modal UX.
- It still shows only the first rule as its visible fallback, but backend data no longer crashes that screen.
- Editing the same step in classic after adding multiple workspace rules is still a risky rollback seam and should not be treated as parity-complete UX.

### Checks

- `.\.venv\Scripts\python.exe -m compileall app tests`
- `.\.venv\Scripts\python.exe -m unittest tests.test_scenario_engine_smoke tests.test_messaging_identity tests.test_employee_api_smoke tests.test_scenario_engine_branching -v`
- `npm run build`

## Survey Workspace Copy And Token Pass - 2026-06-09

### Changed

- Survey workspace labels are shorter in their existing context: `Вопросы`, `Создать`, `Добавить`, `Найти`.
- Main workspace columns now inherit the shared `Card` radius instead of overriding it with a smaller page-local radius.
- At desktop widths up to 1400 px, side columns shrink to preserve a usable central question canvas instead of compressing it to roughly 210 px.
- Success feedback now uses semantic theme tokens instead of raw Tailwind emerald colors.
- Shared `Input` and `Textarea` now set `text-foreground` explicitly, so browser form-control defaults cannot leave light-theme text colors active after switching to dark theme.

### Screens

- `/app/surveys/workspace`
- `/app/flows/workspace-v2`

### Shared UI API

- `Input` and `Textarea` behavior is unchanged; their text color is now explicitly tokenized.

### Checks

- `npm run build`

## Employee Scheduled Delete Confirm - 2026-06-16

### Changed

- Scheduled scenario deletion on `/app/employees/{employee_id}` now uses shared `ConfirmAction` and shadcn/Base `AlertDialog` instead of browser `window.confirm`.
- `ScenarioList` accepts optional confirm metadata for dense icon actions; actions without confirm metadata keep direct execution.

### Screens

- `/app/employees/{employee_id}`

### Shared UI API

- `ConfirmAction` API unchanged.
- `ScenarioList` item shape gained optional `extraActionConfirmTitle`, `extraActionConfirmDescription`, and `extraActionConfirmLabel`.

### Known issues

- Other employee-detail destructive actions still contain legacy `window.confirm` and should be migrated separately if they enter current UX scope.

### Checks

- `npm run build`
- `D:\HRBot\hr_bot\.venv\Scripts\python.exe -m compileall app tests`
- `D:\HRBot\hr_bot\.venv\Scripts\python.exe -m unittest tests.test_scenario_engine_smoke tests.test_messaging_identity tests.test_employee_api_smoke -v`
- Browser smoke on `http://127.0.0.1:8001/app/employees/1`: scheduled scenario delete opens shared `AlertDialog`; no console errors.

## React Admin Confirm Sweep - 2026-06-16

### Changed

- Remaining React admin `window.confirm` calls were replaced with shared `ConfirmAction`.
- Scenario/survey workspace now uses shadcn/Base `AlertDialog` for step/question deletion, attachment deletion, and bulk scenario/survey deletion.
- Bulk actions scheduled-action deletion now uses `ConfirmAction`.
- Employee detail file/link deletion, candidate promotion, and employee deletion now use `ConfirmAction`.

### Screens

- `/app/flows/workspace-v2`
- `/app/surveys/workspace`
- `/app/bulk-actions`
- `/app/employees/{employee_id}`

### Known issues

- Legacy fallback `scenario_edit.html` still has native browser confirm prompts. That surface is behind the explicit legacy seam and needs a separate non-React modal cleanup if it remains supported.

### Checks

- `npm run build`
- `D:\HRBot\hr_bot\.venv\Scripts\python.exe -m compileall app tests`
- `D:\HRBot\hr_bot\.venv\Scripts\python.exe -m unittest tests.test_scenario_engine_smoke tests.test_messaging_identity tests.test_employee_api_smoke -v`
- Browser smoke on `http://127.0.0.1:8002/app/flows/workspace-v2`: step delete opens shared `AlertDialog`; no console errors.
- `rg "window\.confirm|confirm\(" frontend\src app\static\workspace_v2`: no runtime React matches outside design-system documentation text.
