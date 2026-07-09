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
- Delivery model: параллельная работа субагентов теперь разделена на feature-фазу и integration-фазу. Субагенты пушат отдельные feature-ветки, интегратор собирает общий `stage` ref, а GitHub Actions `Deploy Stage` запускается вручную с `ref=stage`.
- Stage deploy теперь обязан создавать проверенный SQLite backup до checkout/restart и сверять fingerprint конфигурации сценариев до/после запуска сервисов.

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
- `/app/dashboard` теперь является default entry для авторизованного оператора: `/`, успешный login и бренд в sidebar ведут на оперативный read-only dashboard без отдельного пункта “Главная” в primary nav.
- React default surfaces включены для `/app/dashboard`, `/login`, `/app/settings`, `/app/bulk-actions` и `/app/surveys/workspace` с shared UI primitives, JSON/API или native auth POST там, где это уместно.
- Sidebar упрощен: отдельная ссылка `Кандидаты` убрана, сотрудники и кандидаты остаются внутри общей React employees surface.
- В `frontend` инициализирован shadcn `components.json`, добавлен широкий набор shadcn `ui/*` компонентов; текущий источник цветов — `frontend/src/index.css` с Tailwind v4 `@theme inline`, OKLCH tokens, semantic `success/warning/info` и light/dark class strategy.
- Текущий frontend UI stack зафиксирован как Base UI first (`base-nova`, `@base-ui/react`) в `docs/features/shadcn-component-contract.md`; новые Radix wrappers запрещены. Existing Radix debt еще остается в отдельных legacy wrappers и требует поэтапной миграции.
- Для admin UI принят обязательный shadcn workflow gate: перед изменением компонента или page composition нужно сверять `npx shadcn@latest info --json`, читать `npx shadcn@latest docs <component>` и локальный `frontend/src/components/ui/*`, а новые page patterns сначала фиксировать во внутреннем `/app/design-system#patterns`.
- Попытка закрепить отдельную `/app/ui-kit` страницу как reference route была отменена: она не уменьшила хаос в создании страниц и была удалена из runtime.
- Вместо этого `/app/design-system` теперь закреплен как внутренний frontend baseline по прямой ссылке: страница должна документировать реальные shared primitives, page patterns и review rules, а не быть отдельной декоративной витриной или operator-facing страницей sidebar. Auth form зафиксирован как pre-auth page pattern и применяется на `/login`.
- Главная frontend-проблема сейчас не отсутствие витрины компонентов, а отсутствие жесткой композиции экранов: часть страниц перегружена в `main.tsx` или крупных page-файлах. `employee detail` уже переехал в Vite-стек и прошел первый structural split (`main.tsx + page.tsx + sections.tsx + helpers.ts`), но это еще не финальная нормализация shared/UI API.
- `frontend/src/employees-list/` уже разрезан по новой схеме (`main.tsx` + `page.tsx` + `components.tsx` + `data.ts` + `types.ts`) и теперь служит первым живым шаблоном для следующих React-экранов.
- `frontend/src/scenario-workspace/` уже прошел первый structural pass: `main.tsx` стал bootstrap-only, экран вынесен в `page.tsx`, а model helpers и picker-компоненты вынесены в отдельные файлы. Сам экран все еще слишком большой, но слой mount и часть технической мешанины уже отделены.
- `frontend/src/scenario-workspace/page.tsx` уже дополнительно разрезан по крупным visual sections: sidebar и центральная колонка вынесены в `sections.tsx`. Основной remaining hotspot теперь detail-pane и его form logic.
- Detail-pane `scenario-workspace` тоже вынесен из `page.tsx` в отдельный section-компонент внутри `sections.tsx`; `employee detail` вслед за ним уже прошел через `helpers.ts` и `sections.tsx`. Основной remaining hotspot теперь не сама файловая структура, а cleanup legacy visual/API drift и безопасное выключение classic fallback routes.
- `frontend/src/bulk-actions/` тоже больше не держит весь экран в `main.tsx`: entrypoint стал bootstrap-only, экран вынесен в `page.tsx`, а usage `Button` приведен к реальному shared API (`destructive` вместо несуществующего `danger`).
- `frontend/src/dashboard/` добавлен как новый bootstrap/page/types surface; он показывает ближайшие scheduled launches/actions, свежие Telegram-привязки кандидатов, inbound files, attention items и module links через `GET /api/dashboard/workspace`.
- `frontend/src/settings/` тоже переведен в `bootstrap + page`: теперь основные React operator screens больше не упираются в большие `main.tsx`, и следующий шаг уже не очередной mechanical split, а cleanup fallback routes и remaining API drift.
- В `tests/test_employee_api_smoke.py` добавлен parity smoke для React write-flow: employee detail updates, bulk-actions preview/schedule и settings workspace mutations проходят через реальный authenticated API client. Это не закрывает route cleanup автоматически, но наконец дает страховку перед отключением classic fallback surfaces.
- Classic operator entrypoints `/employees`, `/candidates`, `/bulk-actions`, `/flows`, `/surveys`, `/settings` уже переведены на `303` redirects в React surfaces. Это убирает прямую конкуренцию старых списков и новых экранов, но не удаляет remaining classic edit/export/write fallback URLs.
- Для backend cleanup начат первый безопасный seam: reusable auth/render/access helpers вынесены из `app/main.py` в `app/web/support.py`. Поведение роутов не менялось; цель шага — перестать держать даже базовую web-обвязку в единственном 5k+ строк монолите.
- Employee backend-slice уже отделен дальше support-layer: employee-specific support/model helpers вынесены в `app/web/employees.py`, а React/API employee routes вынесены в `app/web/employee_routes.py` через `APIRouter`. `app/main.py` больше не держит employee redirects, React bootstrap routes и employee JSON API в одном файле.
- Bulk-actions backend-slice тоже уже отделен на React/API уровне: targeting/workspace helpers вынесены в `app/web/bulk_actions.py`, а `/bulk-actions`, `/app/bulk-actions` и `/api/bulk-actions*` плюс classic bulk form routes вынесены в `app/web/bulk_action_routes.py`.
- Settings backend-slice тоже уже отделен на React/API уровне: HR settings, menu sets/buttons и accounts workspace helpers вынесены в `app/web/settings.py`, а `/settings`, `/app/settings`, `/api/settings*`, `/api/accounts*` и classic settings form handlers вынесены в `app/web/settings_routes.py`.
- Bot menu sets больше не являются просто декоративными наборами кнопок: у `BotMenuSet` теперь есть audience-targeting по `employee_scope`, `role_scope` и явному списку `target_employee_ids`; `settings`/`bot-menu` React/API умеют этим управлять, а runtime бота выбирает и открывает только те наборы, которые реально подходят сотруднику или кандидату.
- Bot menu runtime получил явный navigation contract: `/start` всегда отправляет приветствие и возвращает пользователя в root menu set, если он доступен; если меню не настроено, бот больше не шлет системный fallback-текст про отсутствие меню. Подменю ведутся через `Employee.current_menu_path`, а системные кнопки `Назад` и `Главное меню` добавляются runtime-слоем и запрещены для пользовательских кнопок. На `/app/bot-menu` можно выбрать общий fallback root, отдельный root для сотрудников и отдельный root для кандидатов; рассылка главного меню открывает каждому привязанному пользователю его актуальный root по аудитории.
- `/start` запускает первый подходящий сценарий с `trigger_mode=bot_registration` сразу при новой Telegram-привязке карточки. Повторный `/start` не перезапускает registration-сценарий и остается навигационным возвратом в root menu.
- HR lifecycle перестал упираться только в ручной запуск сценариев: candidate status shortlist нормализован вокруг реальных HR-этапов (`Наш отказ`, `HR`, `руководитель`, `тестирование`, `оффер`, `преонбординг`, `отказ кандидата`), а scenario metadata теперь умеет `trigger_mode=candidate_hr_stage` с explicit `candidate_work_stage_trigger`, который backend превращает в `status_transition` launch request при реальном изменении статуса в карточке кандидата.
- Menu sets и audience-targeting уже перестали помещаться в общие системные настройки: для них выделен отдельный React surface `/app/bot-menu`, а `/app/settings` теперь снова отвечает в основном за HR/system settings и account management вместо смешивания с bot-menu редактором.
- Для shared bot materials добавлена отдельная библиотека документов: `/app/documents` хранит общие файлы и ссылки, `DocumentLibraryItem` отделен от employee-specific `employee_files`, а menu buttons получили новый runtime action `send_document`.
- Для ускорения bot-menu сборки поверх этого добавлен scaffold-helper: `/app/documents` теперь умеет по active categories автоматически создавать иерархию обычных `menu sets` (`root -> category -> send_document buttons`), не вводя отдельную document-navigation подсистему.
- Scaffold для document menus больше не одноразовый и не должен плодить дубли: generated sets помечаются `system_tag`, `create` отказывается создавать второй одинаковый root, а `rebuild` пересобирает только свою generated-ветку, не трогая ручные menu sets.
- В runtime сценариев `Назад` уже не просто навигационный костыль: bot хранит короткую историю интерактивных шагов в `scenario_progress.step_history` и отдельный undo-снимок последнего подтвержденного ответа, поэтому возврат теперь откатывает связанное изменение карточки, `candidate_status`, survey answer и загруженный file record, если они были созданы этим последним ответом.
- React employee detail получил отдельный operator reset для bot linkage: без удаления карточки можно очистить Telegram-привязку, active `scenario_progress`, pending launches и `current_menu_set_id`, чтобы один и тот же тестовый сотрудник или кандидат мог заново пройти `/start` и регистрацию в боте.
- Scenario/surveys slice теперь тоже вынесен полностью на уровне operator routes: workspace helpers и classic editor helpers живут в `app/web/scenarios.py`, а `/flows`, `/surveys`, `/app/flows/workspace-v2`, `/app/surveys/workspace`, `/api/flows/workspace*`, classic editor routes `/flows/{id}`, `/surveys/{id}`, classic update/copy/delete form actions и survey export уже сидят в `app/web/scenario_routes.py`.
- Classic employee tails тоже уже вынесены из `app/main.py` в `app/web/employee_routes.py`: server-rendered `/employees/{id}/edit`, classic employee form posts, profile photo/card image, file upload/download/send и offer document link actions теперь сидят рядом с employee router, а не в монолите.
- Classic bulk-actions tails тоже уже вынесены из `app/main.py` в `app/web/bulk_action_routes.py`: schedule/launch/send/delete form routes теперь сидят рядом с bulk router, а не в монолите.
- Classic settings tails тоже уже вынесены из `app/main.py` в `app/web/settings_routes.py`: HR settings form, menu set/button CRUD, bulk button saves и classic account management теперь сидят рядом с settings router, а не в монолите.
- Swagger/OpenAPI теперь намеренно API-only: `/docs`, alias `/swagger` и `/openapi.json` показывают только JSON routes под `/api/*`, а browser/form/React bootstrap/download surfaces остаются в [[web-surface]].
- По уведомлениям зафиксирована рабочая продуктовая граница на потом: сценарные уведомления не должны переопределяться глобальными настройками; глобальный слой должен отвечать за системные события и delivery rules, а не за смысл конкретного сценария.
- Scenario notification recipients теперь поддерживают системный token `hr`: React workspace показывает HR из `HrSettings`, если задан `telegram_user_id`, а runtime резолвит `hr` в этот Telegram chat id без заведения HR как фейкового сотрудника.
- В scenario runtime закрыт один из главных semantic drifts: обычный step с `response_type=launch_scenario` теперь действительно завершает текущий сценарий и запускает target scenario, а не зависает после своей отправки.
- В scenario runtime добавлен `response_type=date`: бот показывает inline-календарь на кнопках, выбранная дата приходит callback-ом и может сохраняться в `first_workday`. Это контролируемый MVP-ввод даты без свободного текста; нативного Telegram date picker для обычных ботов нет.
- Scheduler для time-based сценариев теперь догоняет первый непройденный шаг в день активации: если сценарий стал активен сегодня, но время первого шага уже прошло, первый шаг ставится на немедленную отправку. При этом `send_step` больше не ставит внутренний `FlowLaunchRequest` для следующего `specific_time` шага, если текущий timed step пришел из scheduler.
- Scheduled delivery теперь финально валидируется прямо перед отправкой: если карточка уже сменила `employee_stage`/scope или у time-based сценария больше нет валидного anchor, старый job/request silently отбрасывается и не доезжает до Telegram.
- React scenario workspace получил следующий обязательный guardrail: название сценария теперь редактируется в settings, список сценариев фильтруется по аудитории `сотрудники/кандидаты`, а select `Переход к сценарию` больше не выглядит доступным при несовместимом `response_type`.
- Sidebar scenario workspace больше не держится за неочевидный backend order как будто это “естественная сортировка”: в payload добавлены timestamp slots `created_at/updated_at`, а UI уже умеет явно сортировать сценарии по недавнему изменению, созданию и алфавиту.
- Employee list/detail launch audit очищен от внутреннего scheduler-макияжа: follow-up jobs с `skip_step_key=__single_step__:*` больше не показываются оператору как будто это отдельные planned launches.
- Ручной запуск сценария из карточки сотрудника больше не создает скрытый pending `manual` request для продолжения после первого non-interactive step. Продолжение снова делает сам engine через нормальные follow-up semantics вместо pseudo-demo очереди на `MANUAL_STEP_MINUTES`.

## Активные проблемы

- Новый scenario workspace функционально богатый, но тяжелый и с лагами.
- Общая frontend build-chain сейчас чувствительна к параллельной работе над `/app/design-system`: после фикса scenario workspace `npm run build` все еще может падать из-за unrelated import errors внутри `frontend/src/design-system/*`. Это не блокер для логики сценариев, но реальный cross-track риск, пока дизайн и основная админка собираются одним Vite build.
- Candidate-to-employee transition уже больше не полностью ручной хаос: в React employee detail появился явный HR cutover `candidate -> adaptation`, который требует `first_workday`, seed-ит `adaptation_midpoint` / `adaptation_end` и очищает candidate-only stage. Но auto-transition по факту “согласился на оффер в боте” все еще сознательно не реализован и остается отдельным продуктовым решением.
- Classic и React employee cards все еще требуют broader correctness pass beyond fixed shared fields.
- Classic UI все еще содержит fallback-экраны и form actions, но ownership этих хвостов уже вынесен из монолита: classic employee, bulk, settings, scenario и survey routes больше не живут в `app/main.py`. Survey export остается non-JSON download route и пока осознанно сохраняется как classic surface.
- Мертвые classic list templates уже удалены из `app/templates`: `scenarios.html`, `mass_actions.html`, `settings.html` больше не имеют route ownership и не должны возвращаться как “временный fallback”. Из classic HTML pages живым edit surface остается только `scenario_edit.html`.
- Classic employee action redirects уже переведены на React detail surface `/app/employees/{id}`: `react_employee_edit.html` принимает `flash_message/flash_type`, React page показывает top-level flash banner, direct GET `/employees/{id}/edit` тоже теперь редиректит в React, а `employee_edit.html` удален из runtime и репозитория.
- Employee detail получил еще один practical parity-pass: React карточка теперь умеет удалять employee files через `DELETE /api/employees/{id}/files/{file_id}` и удаляет document links по конкретной строке, а не через “первую попавшуюся” ссылку.
- React employee detail перестал терять уже существующие данные launch-аудита: `manual_launch_history` из backend payload теперь реально показывается отдельным блоком истории ручных запусков, а smoke-тест фиксирует этот контракт.
- Для основных React surfaces добавлен route-contract smoke: `tests/test_employee_api_smoke.py` теперь явно сверяет существование всех frontend `fetch` endpoints для login, employees, employee detail, bulk-actions, settings и scenario workspace. Это не заменяет behavioral tests, но убирает класс тупых регрессий “UI зовет route, которого больше нет”.
- Employee detail также очищен от ложных `PlannedField`-заглушек в блоке сопровождения: новая карточка больше не притворяется, что поддерживает поля без data contract и сохранения. Это намеренное сужение до реального MVP behavior, а не потеря готовой функции.
- React employee detail получил рабочий adaptation contract вместо placeholder-макета: руководитель, наставник адаптации и наставник ИПР теперь выбираются через select из сотрудников со статусом `staff`; добавлены реальные поля `adaptation_tasks_url`, `adaptation_feedback_url`, `adaptation_midpoint`, `adaptation_end`, а `mid_probation` / `end_probation` сценарные триггеры теперь предпочитают эти явные даты вместо слепого расчета только от `first_workday`.
- Персональные document tags в сценариях больше не должны зависеть только от голой ссылки в карточке: для оффера введен явный employee document slot `offer`, который в React employee detail снова показывается как отдельный продуктовый блок `Оффер`, но под капотом остается частью общей document-модели. Слот умеет быть и ссылкой, и загруженным файлом; `{doc:Оффер}` в runtime по-прежнему совместим с legacy title, а file-backed slot теперь дополнительно отправляет сам файл в Telegram.
- До этого menu sets были архитектурно обманчивыми: оператор мог создавать несколько наборов, но бот не умел сегментировать аудиторию и просто держался за `current_menu_set_id` или global default. Этот риск снят: menu targeting теперь enforced на backend/runtime, а не только в настройках UI.
- Старый `current_menu_set_id` без стека был недостаточен для nested menu UX: пользователь мог застрять в подменю, а `/start` не гарантировал возврат к главному набору. Теперь это закрыто через root menu resolution, `current_menu_path` и runtime-only navigation buttons.
- Дополнительная cleanup-граница тоже уже принята: stage-targeting для menu sets убран как излишне запутывающий слой. Для bot menu остаются только аудитория, должность и точечный список сотрудников/кандидатов, причем один и тот же человек не должен одновременно сидеть в двух разных explicit menu sets.
- Редактор bot-menu кнопок теперь отражает реальный runtime contract: `launch_scenario`, `open_set` и `send_document` являются взаимоисключающими целями, неактуальные селекты disabled, а при смене действия несовместимые значения очищаются.
- Риск следующего уровня теперь другой: если снова складывать menu sets, audience rules, mini app gating и системные HR settings в один экран `/app/settings`, он снова превратится в свалку несвязанных конфигов. Новый baseline: bot menu configuration живет отдельно на `/app/bot-menu`.
- React scenario/survey workspace теперь тоже понимает `flash_message/flash_type`: `react_scenario_workspace_v2.html` прокидывает flash attrs в Vite page, а `scenario-workspace/page.tsx` показывает top-level flash banner перед canvas layout.
- В `scenario-workspace/page.tsx` уже был пойман и исправлен runtime TDZ-баг: экран использовал `payload` до объявления React state, из-за чего workspace мог падать целиком и оставлять на странице только статический shell с кнопкой `Классический список`.
- Safe classic scenario/survey redirects уже частично переведены на React workspace: create/copy/delete flows ведут в `/app/flows/workspace-v2` или `/app/surveys/workspace` с выбранным `scenario_id` и flash message. При этом explicit legacy seam теперь стал внутренне согласованным: если оператор открыл `scenario_edit.html` через `?legacy=1`, то save/delete-attachment/export-error redirects остаются в legacy editor, а не выбрасывают в React случайно.
- Один из главных scenario parity gaps уже закрыт: React workspace теперь читает и сохраняет per-button notifications через `button_notifications`, а `/api/flows/workspace/steps/{id}` синхронизирует `StepButtonNotification` без classic form submit. Это не убирает `scenario_edit.html` целиком, но сужает его реальную ценность до remaining legacy update-flow edges.
- Per-button notifications в React workspace больше не ограничены одной записью на кнопку: у каждой кнопки теперь есть список notification rules с add/edit/delete через modal workflow. Важная backend-граница тоже исправлена: explicit recipients из React больше не притворяются raw chat ids, а сохраняются как `employee:{id}` tokens и резолвятся в реальные chat ids только в runtime.
- React workspace теперь так же умеет редактировать и step-level notifications как список правил, а не как один плоский набор полей. Для этого добавлена отдельная сущность `StepSendNotification`: runtime отправляет все правила по порядку, copy/delete flows сценариев сохраняют эти правила, а legacy `notify_on_send_*` поля оставлены только как compatibility seam для first-rule fallback.
- Branching model стал менее тупиковым: branch-step теперь может вернуть пользователя в root-step того же сценария через `return_to_step_key`, поэтому fork-then-merge кейсы больше не требуют заталкивать весь общий хвост в branch-chain глубину или резать процесс на искусственные отдельные сценарии.
- В React scenario workspace восстановлен самостоятельный тип ответа `buttons`: редактор больше не маскирует его под `branching`. При этом и `buttons`, и `branching` могут сохранять выбранный вариант в `target_field` вроде `salary_expectation`; runtime/API/editor contract покрыт smoke-тестами.
- Проверено, что apparent loss step-level notification rules возникает при рассинхронизации нового frontend bundle со старым непререзапущенным backend-процессом: новый API contract сохраняет rules корректно, regression smoke теперь покрывает и повторное редактирование существующего списка.
- Survey workspace больше не притворяется “сценарием с урезанным UI”. Для опросов question flow теперь принудительно нормализован: один вопрос как единая сущность (`title/text` синхронизируются), `send_mode` всегда `immediate`, `launch_scenario`/`target_field`/step notifications очищаются, а варианты ответа живут как список текстовых option buttons без branching semantics.
- По сценариям остался честный runtime gap, а не путаница в UI: attachment-only interactive steps все еще могут требовать отдельное helper-message, потому что текущий messenger transport не умеет captions + inline markup на document/photo. Это уже не тот же класс бага, что прежний сервисный шум `Выберите вариант ответа:` для обычного text+attachment шага.
- В React scenario workspace добавлен базовый editor guardrail против ложных “поломок бота”: карточки шагов и detail-pane теперь явно показывают, блокирует ли выбранный `response_type` поток (`Ждёт ответ`) или это чистый автопереход (`Автопереход`).
- Backend для следующего UX-шага конструктора уже подготовлен: scenario workspace payload теперь отдает `workspace.graph` с read-only node/edge contract, включая empty branch placeholders, return-to-root edges и launch-scenario targets. Это база для отдельного graph-tab без второго источника истины по flow semantics.
- Classic scenario/survey direct GET surfaces тоже уже сужены: `/flows/{id}` и `/surveys/{id}` по умолчанию ведут в React workspace с выбранным `scenario_id`, а legacy editor открывается только через явный rollback seam `?legacy=1`. Это уже не параллельный основной UI, а осознанно спрятанный fallback, причем теперь и его internal redirects согласованы с этим режимом.
- Нормального migration layer все еще нет; SQLite schema может меняться на startup через `_ensure_sqlite_schema()`.
- `Назад` в сценариях теперь закрывает базовый UX-gap исправления последнего ответа, но это все еще не полноценный multi-step undo-layer: terminal branches, несколько уже пройденных шагов подряд и внешние side effects вне текущего progress по-прежнему требуют отдельной продуктовой семантики, если понадобится настоящий rewind.
- Inspected live SQLite уже показывает unresolved schema drift (`media_assets`, `flow_step_templates.media_asset_id`) без поддержки в текущем коде.
- Stage infrastructure truth все еще частично вне репозитория, потому что systemd env и service definitions не codified здесь.
- Stage deploy больше не должен auto-deploy `main`: при параллельной работе это риск перетереть накопительный `stage`. Нормальный deploy ref — `stage` или осознанный `integration/...`.
- Env precedence больше не должна считаться “локальной мелочью”: 16 июня stage-инцидент показал, что `.env` с `DEMO_MODE=true` в рабочей директории плюс runtime `load_dotenv(override=True)` способны незаметно перевести стенд в demo scheduler semantics. Текущий baseline после фикса — runtime env/systemd важнее `.env`, а stage должен явно держать `DEMO_MODE=false`.
- Stage worker health нельзя определять только через `systemctl active`: 15 июня worker получал updates, но не мог отправлять ответы из-за Telegram API connection timeout. Inbound handlers переведены на общий polling `Bot`, а stage health-check должен включать реальный `/start` round-trip и проверку свежих worker logs.
- SQLite на stage остается operational debt: transient `database is locked` между web и worker уже наблюдался на live scheduler path и может приводить к повторным отправкам, если side effect в Telegram успел произойти до записи audit/event в БД. Текущий mitigation — `timeout=30` в SQLAlchemy sqlite connect args, но это не заменяет более надежную delivery/outbox strategy.
- Прямой маршрут stage к Telegram API остается недоступен; текущий operational workaround — RedShield WireGuard с selective route только для Telegram IP. Это восстанавливает web/worker delivery без переноса SSH и web-трафика в VPN, но остается внешней зависимостью и требует контроля при смене Telegram API IP.
- `employee_messenger_accounts.employee_id` пока не защищен foreign key/cascade, а SQLite foreign keys на stage выключены. Из-за этого удаление карточки может оставить orphan identity и блокировать повторную Telegram-привязку; новый reset bot linkage закрывает операторский test flow без удаления записи, но schema-level cleanup все равно остается отдельной задачей.
- Для двух ИП требуется отдельное решение по legal/data boundary: вероятнее всего, раздельные БД/контуры хранения и явное отображение текущего ИП в UI; это нужно подтвердить юридически и оформить в LLD до реализации.
- Security/compliance слой пока не выделен отдельной реализацией: роли, аудит, защита файлов/персональных данных, секреты, backup policy, CSRF/session/rate-limit hardening требуют отдельного прохода после стабилизации основных модулей.
- Auth/access сейчас реализован минимально: два seeded account type `admin` и `hr`, browser cookie с account id, `admin` нужен только для управления аккаунтами, а большинство operator API доступны любой авторизованной роли. Целевая модель для HR/директора/технического администратора еще не выбрана.
- Obsidian Kanban/Canvas/Graph полезны как views и навигация, но остаются риском, если начнут использоваться как параллельные source of truth вместо [[backlog]], [[architecture]] и live docs.
- Legacy global CSS все еще присутствует, но React runtime уже частично отрезан от него: React templates переведены на отдельный `react_base.html` и `app/static/react_shell.css` вместо прямого наследования `base.html`. Следующий cleanup — убрать remaining visual/API drift и не тащить legacy selectors обратно в новые React pages.
- `app/main.py` уже перестал быть 5k-монолитом и сжат примерно до 200 строк composition-root уровня: startup, middleware, auth/session pages и `include_router(...)`. Это сильный шаг вперед, но не повод автоматически удалять все classic fallback surfaces: сначала нужен parity-pass и осознанное решение, какие legacy pages действительно больше не нужны.

## Ближайшие приоритеты

- `HRB-P1-01` довести HR status launches от базового direct trigger до полной product trigger-matrix: сейчас change event уже стартует сценарии, но дальше нужны policy по dedupe/cooldown, richer audit и явное решение по `offer accepted`.
- `HRB-P1-02` привести scenario-to-scenario transition semantics в новом admin к нормальной модели.
- `HRB-P1-03` унифицировать notifications, чтобы new admin мог безопасно заменить old one.
- `HRB-P1-06` уменьшить workspace lag до broader UX work.
- `HRB-P1-07` переключить фокус с route-split на parity/removal: classic route ownership уже вынесен из `main.py`, теперь нужно решать, какие fallback pages и form actions реально еще нужны.
- Следующий практический шаг по bot UX уже не “еще один набор кнопок”, а нормализация access-layer поверх audience menus: mini app, candidate/staff-only actions и role-specific sections должны опираться на тот же targeting contract, а не жить как отдельные скрытые кнопки.
- После выделения `/app/bot-menu` следующий bot UX шаг уже не “передвинуть еще один блок из settings”, а привязать к тому же targeting contract mini app и candidate/staff-only actions, чтобы не появилось второго параллельного access-layer.
- Следующий шаг по document UX не должен быть “пихать все документы в один root menu set”. Базовый contract уже есть: shared document library + `send_document`; теперь нужен product cleanup по категориям, naming и структуре submenu, чтобы меню бота не превратилось в длинную клавиатуру без навигации.
- Отдельный document UX риск внутри employee detail тоже уточнен: не нужно возвращать россыпь отдельных полей под каждый документ. Если продукт просит “спецдокумент в карточке”, целевой путь — именованный slot поверх общей document-модели, а не новый one-off столбец.
- Следующий dashboard-шаг не должен быть “еще больше карточек”: если главная начнет требовать точную историю регистрации в боте или audit событий, сначала нужен отдельный event/audit model, а не догадки из текущих таблиц.
- Для следующего remove-pass уже есть безопасная база: мертвые classic list pages убраны, поэтому дальше решение нужно принимать только по живым fallback detail/edit surfaces, а не по старым спискам.
- Employee detail remove-pass уже фактически закрыт: classic `employee_edit.html` и direct GET `/employees/{id}/edit` больше не нужны как fallback surface. Оставшийся главный legacy-кандидат теперь один — `scenario_edit.html` и его update-flow.
- Для employee detail следующий шаг теперь уже уже не relation/date contract, а product cleanup: решить, нужен ли `manager_position` как отдельное поле или его надо выводить из карточки выбранного руководителя, и отдельно определить, какие adaptation документы должны быть просто ссылками, а какие стоит переводить на first-class file uploads.
- Следующий шаг по employee document slots — определить shortlist именованных slots (`offer`, `adaptation_tasks`, `adaptation_feedback` и т.д.) и их UI/contract, чтобы сценарные `{doc:...}` не опирались на свободное название записи и не требовали новых спецполей в карточке.
- Для employee lifecycle следующий шаг теперь уже не “добавить еще одну кнопку”, а определить, должен ли bot-driven `offer accepted` создавать отдельный статус/событие до перевода в адаптацию. Текущая безопасная модель — явное HR-действие `Перевести в адаптацию`, а не автоматический cutover по ответу в боте.
- Для `scenario_edit.html` уже снят еще один конкретный blocker: per-button notifications больше не являются classic-only фичей. Следующий вопрос теперь уже уже не про “как редактировать уведомления по кнопкам”, а какие именно nested/batch update semantics legacy editor все еще держит уникально.
- Для `scenario_edit.html` снят и второй notification-blocker: step-level notifications тоже перестали быть classic-only плоской формой. Следующий вопрос теперь не “как завести несколько уведомлений у шага”, а нужен ли legacy editor вообще после закрытия remaining nested update seams.
- Следующий вопрос по branching теперь уже уже не “как вернуться из ветки в основной поток”, а где остановить мощность редактора: текущая модель сознательно разрешает только `branch -> root step` того же сценария, без произвольных графовых прыжков между любыми шагами.
- Для survey flow снят отдельный продуктовый перекос: Excel-выгрузка больше не строится как широкая матрица по колонкам-вопросам, а идет плоскими строками `Пользователь ФИО / Вопрос / Ответ`, что ближе к реальной обработке результатов и меньше ломается при изменении структуры опроса.
- Для scenario/survey remove-pass теперь тоже есть безопасный промежуточный слой: create/copy/delete уже возвращают в React workspace, а legacy seam `?legacy=1` больше не распадается после первого submit. Следующий вопрос уже уже не про навигацию, а нужен ли вообще classic `scenario_edit.html` как fallback для remaining nested update behavior.
- После cutover default GET route вопрос по `scenario_edit.html` уже не про navigation ownership, а только про last-resort rollback semantics. Если React workspace закроет remaining nested update behavior, этот seam можно будет удалить целиком без двусмысленности.
- Для `HRB-P1-07` ближайший frontend-шаг теперь не новая reference page, а cleanup после структурной миграции: React shell уже отделен от legacy `styles.css`, основные React pages разрезаны, smoke на ключевые write-flow добавлен, а legacy operator entrypoints уже редиректят в React. Следующий слой — точечно убирать remaining classic edit/list fallback URLs там, где parity уже достаточна.
- Для `HRB-P1-07` дополнительно зафиксирован новый operating baseline: `/app/design-system` снова нужен проекту как internal direct-link source of truth для shared UI API, page patterns и future QA/watchdog checks, но не должен показываться обычному админу в sidebar на тестовом стенде.
- Для backend-слоя главный structural шаг уже завершен: `main.py` стал composition root, а vertical slices `employees`, `bulk-actions`, `settings`, `scenario/surveys` вынесены в `app/web/*` с green smoke после каждого этапа.
- Следующий backend-шаг теперь не “еще один slice”, а финальный cleanup после декомпозиции: parity-pass remaining classic surfaces, точечное удаление ненужных fallback pages и отдельная нормализация shared helpers/tests там, где ownership уже разнесен.
- После структурных pass по `employees-list`, `scenario-workspace` и `employee detail` следующий frontend-шаг уже не очередной split файлов, а parity-pass и последовательное удаление classic-only хвостов без rollback gap.
- `HRB-DISC-01` выбрать long-term identity-linking flow для existing employees.
- После текущей стабилизации следующий продуктовый модуль — `HRB-P2-06` отпуска MVP; Telegram Mini Apps не начинать как отдельный frontend до решения `HRB-DISC-03` по scope/auth/API boundaries.
- `HRB-DISC-04` определить модель раздельного хранения данных для двух ИП; `HRB-P2-07` не начинать без LLD, потому что это влияет на БД, deploy/runbook, backup и UI context.
- `HRB-DISC-05` определить модель ролей и доступа админки до расширения account management: директору может быть нужен operational доступ без права управлять аккаунтами, а технический `admin` должен быть отделен от ежедневной HR-работы.
- `HRB-P2-08` начат с узкого auth-hardening slice: admin cookie теперь подписанная и с TTL, raw account id больше не авторизует, `/login` имеет базовый rate limit, account management отклоняет слабые новые пароли. Следующий security-шаг для stage — домен + HTTPS reverse proxy + закрытый публичный `:8000`, затем смена `ADMIN_SESSION_SECRET` и `ADMIN_SESSION_COOKIE_SECURE=true`.
- Первые LLD-кандидаты после стандарта: scenario engine, bot identity, employee lifecycle, notification model, schema/migration strategy и React scenario workspace.

## Операционные ограничения

- Classic admin остается fallback source для business continuity и не должен ломаться, пока React screens улучшаются.
- Scenario logic и HR-facing behavior разделены между backend templates, React frontend и bot runtime; изменения требуют cross-surface checks.
- Локальный repo сейчас содержит runtime databases и snapshots outside git; docs должны описывать behavior, а не предполагать чистоту runtime data.
- Для schema questions source of truth — code плюс startup schema guard, а не raw SQLite inspection alone.
- Для docs questions source of truth — [[documentation-standard]]; старые документы можно мигрировать к frontmatter contract постепенно при следующих изменениях.
- Для параллельных субагентов source of truth по веткам и handoff — [[subagent-delivery]]. Не деплоить feature-ветки напрямую на общий stage без явного решения.

## Правило документации

Обновлять этот файл, когда:

- меняются priorities;
- major risk снят или добавлен;
- chosen implementation model подсистемы меняется;
- завершенная задача меняет practical operating state проекта.
- меняется формат документации, Obsidian workflow или границы source of truth.
