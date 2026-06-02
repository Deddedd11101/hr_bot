---
title: Состояние проекта HR Bot
date: 2026-05-14
status: active
doc_type: state
area: core
task_tokens:
  - HRB-DOC-01
  - HRB-DOC-02
  - HRB-DOC-03
  - HRB-DOC-04
  - HRB-P0-01
  - HRB-P0-02
  - HRB-P0-03
  - HRB-P0-04
  - HRB-P0-05
  - HRB-P0-06
  - HRB-P1-06
  - HRB-P1-07
  - HRB-P2-06
  - HRB-P2-07
  - HRB-P2-08
  - HRB-DISC-03
  - HRB-DISC-04
related:
  - "[[README]]"
  - "[[backlog]]"
  - "[[architecture]]"
  - "[[documentation-standard]]"
  - "[[local-runbook]]"
  - "[[roadmap-2026-05-12]]"
  - "[[demo-day-brief-2026-05-12]]"
source_of_truth: true
---

# Состояние проекта

## Текущий snapshot

- Stack: FastAPI admin + Aiogram Telegram bot + APScheduler + SQLite + React/Vite admin surfaces.
- Production model: classic admin pages остаются рабочими fallback-экранами, пока новые React-экраны развиваются параллельно.
- Documentation model: `docs/` — git-backed project vault; live runtime truth разделен по architecture, API, web surface, data model, stage deploy и configuration docs.
- Documentation standard: введен легкий формат docs, templates и maps; Obsidian используется как navigation/properties/templates layer, а canonical truth остается Markdown в git.
- Local run model: рабочая команда запуска админки зафиксирована в [[local-runbook]]; запуск без `--reload` является основной командой.
- UI migration model: принят LLD-подход для перевода classic admin UI на React default с сохранением classic direct routes как временного rollback.

## Что работает

- Карточки сотрудников и кандидатов есть и в classic, и в React admin surfaces.
- Scenario templates, step templates, branching, chain steps и manual launches уже реализованы.
- Telegram bot умеет отправлять шаги, собирать text/files/button responses и писать progress в SQLite.
- Mass actions, onboarding scheduler и scenario portability tooling уже есть в коде.
- Unknown Telegram users больше не создают candidate records автоматически.
- Bot access можно заблокировать per employee через `is_bot_blocked`.
- Incoming Telegram photos обрабатываются как first-class inbound files вместе с documents.
- Mass actions могут target employee stages и candidate stages отдельно.
- В репозитории теперь есть explicit live docs для JSON API, operator web routes, schema behavior, env/config и текущего stage deploy path.
- Для новых и существенно обновленных docs зафиксирован frontmatter contract, doc types, LLD/ADR/runbook rules и Obsidian practices.
- Есть LLD для миграции classic admin UI на React, включая приоритет страниц и карту form routes, которые нужно заменить JSON API.
- React default entry включен для root/login/sidebar; `/app/settings`, `/app/bulk-actions` и `/app/surveys/workspace` реализованы как React slices/workspace modes с JSON API и classic fallback.
- Sidebar упрощен: отдельная ссылка `Кандидаты` убрана, сотрудники и кандидаты остаются внутри общей React employees surface.
- В `frontend` инициализирован shadcn `components.json`, добавлен широкий набор shadcn `ui/*` компонентов; текущий источник цветов — `frontend/src/index.css` с Tailwind v4 `@theme inline`, OKLCH tokens, semantic `success/warning/info` и light/dark class strategy.
- Текущий frontend UI stack зафиксирован как Base UI first (`base-nova`, `@base-ui/react`) в `docs/features/shadcn-component-contract.md`; новые Radix wrappers запрещены. Existing Radix debt еще остается в отдельных legacy wrappers и требует поэтапной миграции.
- Попытка закрепить отдельную `/app/ui-kit` страницу как reference route была отменена: она не уменьшила хаос в создании страниц и была удалена из runtime.
- Вместо этого `/app/design-system` теперь закреплен как живой frontend baseline: страница должна документировать реальные shared primitives, page patterns и review rules, а не быть отдельной декоративной витриной.
- Главная frontend-проблема сейчас не отсутствие витрины компонентов, а отсутствие жесткой композиции экранов: часть страниц перегружена в `main.tsx` или крупных page-файлах. `employee detail` уже переехал в Vite-стек и прошел первый structural split (`main.tsx + page.tsx + sections.tsx + helpers.ts`), но это еще не финальная нормализация shared/UI API.
- `frontend/src/employees-list/` уже разрезан по новой схеме (`main.tsx` + `page.tsx` + `components.tsx` + `data.ts` + `types.ts`) и теперь служит первым живым шаблоном для следующих React-экранов.
- `frontend/src/scenario-workspace/` уже прошел первый structural pass: `main.tsx` стал bootstrap-only, экран вынесен в `page.tsx`, а model helpers и picker-компоненты вынесены в отдельные файлы. Сам экран все еще слишком большой, но слой mount и часть технической мешанины уже отделены.
- `frontend/src/scenario-workspace/page.tsx` уже дополнительно разрезан по крупным visual sections: sidebar и центральная колонка вынесены в `sections.tsx`. Основной remaining hotspot теперь detail-pane и его form logic.
- Detail-pane `scenario-workspace` тоже вынесен из `page.tsx` в отдельный section-компонент внутри `sections.tsx`; `employee detail` вслед за ним уже прошел через `helpers.ts` и `sections.tsx`. Основной remaining hotspot теперь не сама файловая структура, а cleanup legacy visual/API drift и безопасное выключение classic fallback routes.
- `frontend/src/bulk-actions/` тоже больше не держит весь экран в `main.tsx`: entrypoint стал bootstrap-only, экран вынесен в `page.tsx`, а usage `Button` приведен к реальному shared API (`destructive` вместо несуществующего `danger`).
- `frontend/src/settings/` тоже переведен в `bootstrap + page`: теперь основные React operator screens больше не упираются в большие `main.tsx`, и следующий шаг уже не очередной mechanical split, а cleanup fallback routes и remaining API drift.
- В `tests/test_employee_api_smoke.py` добавлен parity smoke для React write-flow: employee detail updates, bulk-actions preview/schedule и settings workspace mutations проходят через реальный authenticated API client. Это не закрывает route cleanup автоматически, но наконец дает страховку перед отключением classic fallback surfaces.
- Classic operator entrypoints `/employees`, `/candidates`, `/bulk-actions`, `/flows`, `/surveys`, `/settings` уже переведены на `303` redirects в React surfaces. Это убирает прямую конкуренцию старых списков и новых экранов, но не удаляет remaining classic edit/export/write fallback URLs.
- Для backend cleanup начат первый безопасный seam: reusable auth/render/access helpers вынесены из `app/main.py` в `app/web/support.py`. Поведение роутов не менялось; цель шага — перестать держать даже базовую web-обвязку в единственном 5k+ строк монолите.
- Employee backend-slice уже отделен дальше support-layer: employee-specific support/model helpers вынесены в `app/web/employees.py`, а React/API employee routes вынесены в `app/web/employee_routes.py` через `APIRouter`. `app/main.py` больше не держит employee redirects, React bootstrap routes и employee JSON API в одном файле.
- Bulk-actions backend-slice тоже уже отделен на React/API уровне: targeting/workspace helpers вынесены в `app/web/bulk_actions.py`, а `/bulk-actions`, `/app/bulk-actions` и `/api/bulk-actions*` плюс classic bulk form routes вынесены в `app/web/bulk_action_routes.py`.
- Settings backend-slice тоже уже отделен на React/API уровне: HR settings, menu sets/buttons и accounts workspace helpers вынесены в `app/web/settings.py`, а `/settings`, `/app/settings`, `/api/settings*`, `/api/accounts*` и classic settings form handlers вынесены в `app/web/settings_routes.py`.
- Scenario/surveys slice теперь тоже вынесен полностью на уровне operator routes: workspace helpers и classic editor helpers живут в `app/web/scenarios.py`, а `/flows`, `/surveys`, `/app/flows/workspace-v2`, `/app/surveys/workspace`, `/api/flows/workspace*`, classic editor routes `/flows/{id}`, `/surveys/{id}`, classic update/copy/delete form actions и survey export уже сидят в `app/web/scenario_routes.py`.
- Classic employee tails тоже уже вынесены из `app/main.py` в `app/web/employee_routes.py`: server-rendered `/employees/{id}/edit`, classic employee form posts, profile photo/card image, file upload/download/send и offer document link actions теперь сидят рядом с employee router, а не в монолите.
- Classic bulk-actions tails тоже уже вынесены из `app/main.py` в `app/web/bulk_action_routes.py`: schedule/launch/send/delete form routes теперь сидят рядом с bulk router, а не в монолите.
- Classic settings tails тоже уже вынесены из `app/main.py` в `app/web/settings_routes.py`: HR settings form, menu set/button CRUD, bulk button saves и classic account management теперь сидят рядом с settings router, а не в монолите.
- Swagger/OpenAPI теперь намеренно API-only: `/docs`, alias `/swagger` и `/openapi.json` показывают только JSON routes под `/api/*`, а browser/form/React bootstrap/download surfaces остаются в [[web-surface]].

## Активные проблемы

- Новый scenario workspace функционально богатый, но тяжелый и с лагами.
- Общая frontend build-chain сейчас чувствительна к параллельной работе над `/app/design-system`: после фикса scenario workspace `npm run build` все еще может падать из-за unrelated import errors внутри `frontend/src/design-system/*`. Это не блокер для логики сценариев, но реальный cross-track риск, пока дизайн и основная админка собираются одним Vite build.
- Candidate-to-employee transition и identity linking для existing employees все еще нерешенные продуктовые решения.
- Classic и React employee cards все еще требуют broader correctness pass beyond fixed shared fields.
- Classic UI все еще содержит fallback-экраны и form actions, но ownership этих хвостов уже вынесен из монолита: classic employee, bulk, settings, scenario и survey routes больше не живут в `app/main.py`. Survey export остается non-JSON download route и пока осознанно сохраняется как classic surface.
- Мертвые classic list templates уже удалены из `app/templates`: `scenarios.html`, `mass_actions.html`, `settings.html` больше не имеют route ownership и не должны возвращаться как “временный fallback”. Из classic HTML pages живым edit surface остается только `scenario_edit.html`.
- Classic employee action redirects уже переведены на React detail surface `/app/employees/{id}`: `react_employee_edit.html` принимает `flash_message/flash_type`, React page показывает top-level flash banner, direct GET `/employees/{id}/edit` тоже теперь редиректит в React, а `employee_edit.html` удален из runtime и репозитория.
- React employee detail получил visual reset под shared UI baseline: экран больше не использует старые hover-heavy `react-section` блоки, документы разведены на HR/outbound и employee/inbound зоны, а новые реквизиты адаптации показаны как disabled contract до backend-поддержки.
- React scenario/survey workspace теперь тоже понимает `flash_message/flash_type`: `react_scenario_workspace_v2.html` прокидывает flash attrs в Vite page, а `scenario-workspace/page.tsx` показывает top-level flash banner перед canvas layout.
- В `scenario-workspace/page.tsx` уже был пойман и исправлен runtime TDZ-баг: экран использовал `payload` до объявления React state, из-за чего workspace мог падать целиком и оставлять на странице только статический shell с кнопкой `Классический список`.
- Safe classic scenario/survey redirects уже частично переведены на React workspace: create/copy/delete flows ведут в `/app/flows/workspace-v2` или `/app/surveys/workspace` с выбранным `scenario_id` и flash message. При этом explicit legacy seam теперь стал внутренне согласованным: если оператор открыл `scenario_edit.html` через `?legacy=1`, то save/delete-attachment/export-error redirects остаются в legacy editor, а не выбрасывают в React случайно.
- Один из главных scenario parity gaps уже закрыт: React workspace теперь читает и сохраняет per-button notifications через `button_notifications`, а `/api/flows/workspace/steps/{id}` синхронизирует `StepButtonNotification` без classic form submit. Это не убирает `scenario_edit.html` целиком, но сужает его реальную ценность до remaining legacy update-flow edges.
- Classic scenario/survey direct GET surfaces тоже уже сужены: `/flows/{id}` и `/surveys/{id}` по умолчанию ведут в React workspace с выбранным `scenario_id`, а legacy editor открывается только через явный rollback seam `?legacy=1`. Это уже не параллельный основной UI, а осознанно спрятанный fallback, причем теперь и его internal redirects согласованы с этим режимом.
- Нормального migration layer все еще нет; SQLite schema может меняться на startup через `_ensure_sqlite_schema()`.
- Inspected live SQLite уже показывает unresolved schema drift (`media_assets`, `flow_step_templates.media_asset_id`) без поддержки в текущем коде.
- Stage infrastructure truth все еще частично вне репозитория, потому что systemd env и service definitions не codified здесь.
- Для двух ИП требуется отдельное решение по legal/data boundary: вероятнее всего, раздельные БД/контуры хранения и явное отображение текущего ИП в UI; это нужно подтвердить юридически и оформить в LLD до реализации.
- Security/compliance слой пока не выделен отдельной реализацией: роли, аудит, защита файлов/персональных данных, секреты, backup policy, CSRF/session/rate-limit hardening требуют отдельного прохода после стабилизации основных модулей.
- Obsidian Kanban/Canvas/Graph полезны как views и навигация, но остаются риском, если начнут использоваться как параллельные source of truth вместо [[backlog]], [[architecture]] и live docs.
- Legacy global CSS все еще присутствует, но React runtime уже частично отрезан от него: React templates переведены на отдельный `react_base.html` и `app/static/react_shell.css` вместо прямого наследования `base.html`. Следующий cleanup — убрать remaining visual/API drift и не тащить legacy selectors обратно в новые React pages.
- `app/main.py` уже перестал быть 5k-монолитом и сжат примерно до 200 строк composition-root уровня: startup, middleware, auth/session pages и `include_router(...)`. Это сильный шаг вперед, но не повод автоматически удалять все classic fallback surfaces: сначала нужен parity-pass и осознанное решение, какие legacy pages действительно больше не нужны.

## Ближайшие приоритеты

- `HRB-P1-01` запускать сценарии из HR status changes вместо manual operator workarounds.
- `HRB-P1-02` привести scenario-to-scenario transition semantics в новом admin к нормальной модели.
- `HRB-P1-03` унифицировать notifications, чтобы new admin мог безопасно заменить old one.
- `HRB-P1-06` уменьшить workspace lag до broader UX work.
- `HRB-P1-07` переключить фокус с route-split на parity/removal: classic route ownership уже вынесен из `main.py`, теперь нужно решать, какие fallback pages и form actions реально еще нужны.
- Для следующего remove-pass уже есть безопасная база: мертвые classic list pages убраны, поэтому дальше решение нужно принимать только по живым fallback detail/edit surfaces, а не по старым спискам.
- Employee detail remove-pass уже фактически закрыт: classic `employee_edit.html` и direct GET `/employees/{id}/edit` больше не нужны как fallback surface. Оставшийся главный legacy-кандидат теперь один — `scenario_edit.html` и его update-flow.
- Для employee detail следующий шаг теперь backend-contract pass: сериализовать category/source документов, добавить relation-пикер наставника, adaptation dates/file links и `manager_position` + `is_manager` условие.
- Для `scenario_edit.html` уже снят еще один конкретный blocker: per-button notifications больше не являются classic-only фичей. Следующий вопрос теперь уже уже не про “как редактировать уведомления по кнопкам”, а какие именно nested/batch update semantics legacy editor все еще держит уникально.
- Для scenario/survey remove-pass теперь тоже есть безопасный промежуточный слой: create/copy/delete уже возвращают в React workspace, а legacy seam `?legacy=1` больше не распадается после первого submit. Следующий вопрос уже уже не про навигацию, а нужен ли вообще classic `scenario_edit.html` как fallback для remaining nested update behavior.
- После cutover default GET route вопрос по `scenario_edit.html` уже не про navigation ownership, а только про last-resort rollback semantics. Если React workspace закроет remaining nested update behavior, этот seam можно будет удалить целиком без двусмысленности.
- Для `HRB-P1-07` ближайший frontend-шаг теперь не новая reference page, а cleanup после структурной миграции: React shell уже отделен от legacy `styles.css`, основные React pages разрезаны, smoke на ключевые write-flow добавлен, а legacy operator entrypoints уже редиректят в React. Следующий слой — точечно убирать remaining classic edit/list fallback URLs там, где parity уже достаточна.
- Для `HRB-P1-07` дополнительно зафиксирован новый operating baseline: `/app/design-system` снова нужен проекту, но уже не как отдельный UI-kit ради демонстрации, а как live source of truth для shared UI API, page patterns и future QA/watchdog checks.
- Для backend-слоя главный structural шаг уже завершен: `main.py` стал composition root, а vertical slices `employees`, `bulk-actions`, `settings`, `scenario/surveys` вынесены в `app/web/*` с green smoke после каждого этапа.
- Следующий backend-шаг теперь не “еще один slice”, а финальный cleanup после декомпозиции: parity-pass remaining classic surfaces, точечное удаление ненужных fallback pages и отдельная нормализация shared helpers/tests там, где ownership уже разнесен.
- После структурных pass по `employees-list`, `scenario-workspace` и `employee detail` следующий frontend-шаг уже не очередной split файлов, а parity-pass и последовательное удаление classic-only хвостов без rollback gap.
- `HRB-DISC-01` выбрать long-term identity-linking flow для existing employees.
- После текущей стабилизации следующий продуктовый модуль — `HRB-P2-06` отпуска MVP; Telegram Mini Apps не начинать как отдельный frontend до решения `HRB-DISC-03` по scope/auth/API boundaries.
- `HRB-DISC-04` определить модель раздельного хранения данных для двух ИП; `HRB-P2-07` не начинать без LLD, потому что это влияет на БД, deploy/runbook, backup и UI context.
- `HRB-P2-08` запланировать security/compliance hardening после стабилизации ключевых модулей; auth, identity и data isolation учитывать уже в LLD для двух ИП и Mini Apps.
- Первые LLD-кандидаты после стандарта: scenario engine, bot identity, employee lifecycle, notification model, schema/migration strategy и React scenario workspace.

## Операционные ограничения

- Classic admin остается fallback source для business continuity и не должен ломаться, пока React screens улучшаются.
- Scenario logic и HR-facing behavior разделены между backend templates, React frontend и bot runtime; изменения требуют cross-surface checks.
- Локальный repo сейчас содержит runtime databases и snapshots outside git; docs должны описывать behavior, а не предполагать чистоту runtime data.
- Для schema questions source of truth — code плюс startup schema guard, а не raw SQLite inspection alone.
- Для docs questions source of truth — [[documentation-standard]]; старые документы можно мигрировать к frontmatter contract постепенно при следующих изменениях.

## Правило документации

Обновлять этот файл, когда:

- меняются priorities;
- major risk снят или добавлен;
- chosen implementation model подсистемы меняется;
- завершенная задача меняет practical operating state проекта.
- меняется формат документации, Obsidian workflow или границы source of truth.
