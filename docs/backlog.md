---
title: Бэклог HR Bot
date: 2026-05-14
status: active
doc_type: backlog
area: docs
task_tokens:
  - HRB-DOC-01
  - HRB-DOC-02
  - HRB-DOC-03
  - HRB-DOC-04
  - HRB-P1-07
  - HRB-P2-06
  - HRB-P2-07
  - HRB-P2-08
  - HRB-DISC-03
  - HRB-DISC-04
related:
  - "[[README]]"
  - "[[project_state]]"
  - "[[documentation-standard]]"
source_of_truth: true
---

# Бэклог HR Bot

Stage candidate: персональный slot `offer` поддерживает ссылку или файл без добавления нового one-off поля в карточку.

Словарь статусов:

- `todo` — согласовано, но не начато
- `doing` — в работе
- `done` — реализовано и задокументировано
- `blocked` — остановлено из-за зависимости или нерешенного решения

## Документация

| Token | Статус | Название | Описание | Ссылки |
| --- | --- | --- | --- | --- |
| `HRB-DOC-01` | `done` | Git-backed Obsidian-документация | `docs/` структурирован как project vault с live docs и dated history. | [[README]], [[project_state]], [[decisions/obsidian-vault-adoption]], [[handoffs/docs-vault-adoption-handoff]] |
| `HRB-DOC-02` | `done` | Расширение runtime source-of-truth docs | Добавлены live docs для JSON API, web surface, data model, stage deploy и configuration; зафиксировано правило, что schema docs строятся code-first плюс observed drift. | [[architecture]], [[api]], [[web-surface]], [[data-model]], [[stage-deploy]], [[configuration]], [[decisions/data-schema-source-of-truth]], [[handoffs/docs-source-of-truth-expansion-handoff]] |
| `HRB-DOC-03` | `done` | Стандарт документации и Obsidian-практики | Введены documentation standard, templates, navigation maps и ADR; Obsidian закреплен как navigation layer, а не отдельный source of truth. | [[documentation-standard]], [[maps/start-here]], [[maps/engineering-map]], [[maps/product-map]], [[decisions/documentation-format-standard]] |
| `HRB-DOC-04` | `done` | Локальный runbook запуска | Зафиксирован текущий рабочий локальный запуск без обязательного `--reload`; корневой README обновлен, `--reload` оставлен только как optional dev-mode. | [[local-runbook]], [[README]] |

## P0

| Token | Статус | Название | Описание |
| --- | --- | --- | --- |
| `HRB-P0-01` | `done` | Жесткая идентификация неизвестного пользователя в боте | Бот больше не создает новых кандидатов по неизвестному Telegram-контакту и вместо этого отвечает короткой инструкцией. |
| `HRB-P0-02` | `done` | Блокировка уволенных сотрудников | Добавлен флаг `is_bot_blocked` с запретом на меню, входящие ответы, файлы и новые сценарии. |
| `HRB-P0-03` | `done` | Тихая обработка лишнего ввода вне сценария | Лишний текст от известного пользователя теперь игнорируется без сервисного шума, но меню-кнопки продолжают работать. |
| `HRB-P0-04` | `done` | Прием входящих файлов и медиа без потерь | Входящий прием расширен до `document` и `photo`, а файлы неизвестных и заблокированных пользователей больше не сохраняются. |
| `HRB-P0-05` | `done` | Корректный массовый таргетинг кандидатов и сотрудников | Массовые действия переведены на split-targeting по `employee_stage` и `candidate_work_stage` с чтением legacy `target_statuses`. |
| `HRB-P0-06` | `done` | Исправление сохранения карточки сотрудника/кандидата | Общие поля карточки, включая `salary_expectation`, теперь сохраняются одинаково из обеих админских поверхностей. |

## P1

| Token | Статус | Название | Описание |
| --- | --- | --- | --- |
| `HRB-P1-01` | `doing` | Запуск сценария по смене HR-статуса | Employee detail теперь умеет запускать сценарии от реальной смены `candidate_work_stage`: у сценария есть `trigger_mode=candidate_hr_stage` и explicit `candidate_work_stage_trigger`, backend ставит `status_transition` launch request и worker запускает обычный `start_scenario(...)`. Следующий шаг — закрыть полную trigger matrix, richer dedupe/cooldown policy и решить, нужен ли отдельный event/status для `offer accepted`, вместо слепого auto-convert из Telegram ответа. |
| `HRB-P1-02` | `doing` | Нормальная семантика перехода к другому сценарию | React workspace уже ушел от однослотовой notification-схемы и для кнопок, и для самих шагов: у обоих появились множественные rules через modal editor, а recipient contract нормализован до explicit employee tokens. Параллельно survey flow перестал маскироваться под полноценный сценарий: question flow теперь текстовый с optional answer variants, без branching semantics. Runtime-переход `launch_scenario` для обычного шага больше не зависает молча: после отправки шага сценарий корректно завершается и стартует target scenario. Дополнительно branch-step теперь умеет вернуться в root-step того же сценария через `return_to_step_key`, чтобы не дожимать весь общий flow внутри chain-веток. Следующий шаг — cleanup remaining classic editor semantics и явное product-правило для пустого target scenario. |
| `HRB-P1-03` | `doing` | Унификация уведомлений | Notification model начала выравниваться: button notifications уже живут в `StepButtonNotification`, step-level notifications переведены в `StepSendNotification`, runtime отправляет все rules по порядку, а explicit recipient contract поддерживает системный token `hr` из `HrSettings.telegram_user_id` без создания фейкового сотрудника. Оставшийся шаг — убрать product ambiguity между сценарными уведомлениями и глобальными system notifications/delivery rules. |
| `HRB-P1-04` | `doing` | Убрать пустые и системные сообщения из сценариев | Новые scenario-шаги, ветки и chain-шаги больше не получают сохраняемый текст-заглушку `Новое сообщение сценария.`; UI должен показывать placeholder, а не подставлять отправляемый текст. Ранее также убран минимум одного класса служебного шума: шаг с текстом, вложением и inline-вариантами больше не шлет отдельное `Выберите вариант ответа:`. Оставшийся scope: не отправлять пустые шаги и убрать другие служебные утечки в диалог. |
| `HRB-P1-05` | `todo` | Аудит доступности сценариев для ручного запуска | Проверить, почему новые сценарии не всегда видны в карточке сотрудника/кандидата. |
| `HRB-P1-06` | `todo` | Performance-pass новой админки сценариев | Уменьшить лаги конструктора без полного редизайна. |
| `HRB-P1-08` | `done` | Оперативный dashboard как главная страница | Добавлен `/app/dashboard` и `GET /api/dashboard/workspace`; `/`, успешный login и sidebar brand ведут на dashboard. Страница read-only: ближайшие scheduled actions, свежие Telegram-привязки кандидатов, inbound files, attention items и module links. Отдельный пункт “Главная” в primary nav не добавлен. |
| `HRB-P1-07` | `doing` | Перенос classic admin UI на React default | LLD зафиксирован; React default entry включен; `/login`, `/app/settings`, `/app/bulk-actions`, `/app/surveys/workspace`, `/app/bot-menu` и `/app/documents` реализованы. Неудачный эксперимент с `/app/ui-kit` удален из runtime: он не помог упростить создание страниц и только добавил лишнюю поверхность поддержки. Вместо этого `/app/design-system` теперь возвращен как live baseline для реальных shared primitives, page patterns и review rules; auth form добавлен как pre-auth pattern. В `frontend` инициализирован shadcn `components.json`, догружен расширенный набор `ui/*` компонентов, добавлен локальный `time-picker`; текущий стек фактически Base UI first, но часть legacy wrappers еще Radix. Основные React operator pages больше не живут как жирные entrypoints: `frontend/src/employees-list/` переведен на `bootstrap + page + local components + data + types`, `frontend/src/scenario-workspace/` разрезан на `main.tsx + page.tsx + model.ts + pickers.tsx + sections.tsx + types.ts`, `employee detail` перенесен в Vite bundle `frontend/src/employee-detail/` и разрезан на `main.tsx + page.tsx + sections.tsx + helpers.ts`, `frontend/src/bulk-actions/`, `frontend/src/settings/`, `frontend/src/bot-menu/`, `frontend/src/documents/` и `frontend/src/login/` тоже переведены на bootstrap/page split. Старые `app/static/react_employee_edit_*` удалены из runtime и репозитория; destructive actions приведены к реальному shared `Button` API (`destructive`, не `danger`). React templates вынесены с legacy `base.html` на отдельный `react_base.html` и `app/static/react_shell.css`, чтобы новые страницы больше не наследовали `app/static/styles.css`; `/login` остается standalone pre-auth shell без sidebar, но грузит общий `workspace_v2/app.css` и `login.js`. Для route cleanup добавлен parity smoke в `tests/test_employee_api_smoke.py`: он покрывает employee detail writes, bulk-actions preview/schedule, settings workspace mutations, document library link creation, bot-menu `send_document`, редиректы legacy operator entrypoints, classic scenario editor legacy seam, default scenario/survey GET redirects, survey export, employee-detail flash redirect flow, employee edit redirect cutover, scenario-workspace flash/create-copy-delete redirects, button-notification sync через workspace API, step-send-notification sync через workspace API, survey question-flow normalization через workspace API, удаление employee files, presence `manual_launch_history` в employee detail payload, reset bot linkage и route-contract existence для всех текущих frontend `fetch` endpoints. В employee detail contract уже не фейковый: руководитель, наставник адаптации и наставник ИПР выбираются из сотрудников со статусом `staff`, в карточке появились реальные поля `adaptation_tasks_url`, `adaptation_feedback_url`, `adaptation_midpoint`, `adaptation_end`, отдельный reset Telegram/runtime linkage для повторной регистрации в боте, а сценарные триггеры `mid_probation` / `end_probation` теперь предпочитают эти даты. Для backend cleanup `app/main.py` доведен до composition-root состояния: reusable auth/render/access helpers вынесены в `app/web/support.py`, employee support/model helpers и classic/react routes — в `app/web/employees.py` + `app/web/employee_routes.py`, bulk-actions helpers и routes — в `app/web/bulk_actions.py` + `app/web/bulk_action_routes.py`, settings helpers и routes — в `app/web/settings.py` + `app/web/settings_routes.py`, shared documents helpers и routes — в `app/web/documents.py` + `app/web/document_routes.py`, scenario/surveys helpers и routes — в `app/web/scenarios.py` + `app/web/scenario_routes.py`. Мертвые classic list templates `scenarios.html`, `mass_actions.html`, `settings.html` уже удалены; `employee_edit.html` тоже удален, direct classic employee GET уже редиректит в React detail, classic employee POST redirects уже возвращают в React detail с flash banner, safe scenario/survey create-copy-delete redirects уже возвращают в React workspace с selected `scenario_id` и flash banner, per-button notifications и step-level notifications больше не являются classic-only функцией, survey flow больше не держит в UI и API лишние scenario-only поля, default `GET /flows/{id}` и `GET /surveys/{id}` уже редиректят в React workspace вместо classic editor, а remaining legacy editor теперь хотя бы внутренне согласован через `?legacy=1`. Дополнительно menu sets перестали быть пустой future-закладкой: audience targeting упрощен до `employee_scope`, `role_scope` и explicit `target_employee_ids`; stage-targeting для menu sets удален как лишний слой, а один и тот же сотрудник/кандидат больше не должен дублироваться в разных explicit наборах. Редактор menu sets вынесен из `/app/settings` в отдельный `/app/bot-menu`, а shared document library — в отдельный `/app/documents`, чтобы системные HR/account settings, bot-menu rules и общие bot materials не смешивались между собой. Bot menu runtime теперь хранит стек подменю в `current_menu_path`, `/start` возвращает пользователя в root-набор, reserved-кнопки `Назад`/`Главное меню` добавляются только runtime-слоем, а `/app/bot-menu` умеет выбрать главный набор и разослать его привязанным пользователям. Следующий риск теперь не в отсутствии страницы, а в том, чтобы не раздвоить helpers между `settings`, `bot-menu` и `documents`, и не превратить меню документов в плоскую длинную клавиатуру без нормальной категоризации. |

### Frontend operating rule

- Для `HRB-P1-07` любые новые admin UI правки обязаны идти через shadcn workflow gate: `npx shadcn@latest info --json`, `npx shadcn@latest docs <component>`, проверка локальных `frontend/src/components/ui/*`, при необходимости `search`/`add --dry-run`/`--diff`, затем сначала internal `/app/design-system#patterns`, потом live page. `/app/design-system` больше не показывается в operator sidebar, чтобы не торчать на тестовом стенде как обычная админская страница.
- React scenario workspace снова сохраняет `response_type=buttons` как самостоятельный тип ответа и не маскирует его под `branching`; и `buttons`, и `branching` шаги с вариантами ответа могут сохранять `target_field`, включая `salary_expectation`.
- `/app/bot-menu` button editor больше не выглядит как три независимые цели одной кнопки: сценарий, переход к набору и документ теперь показаны как взаимоисключающие target-поля с disabled неактуальными селектами.
- `/app/bot-menu` root-menu contract теперь явный: общий fallback, отдельный главный набор для сотрудников и отдельный главный набор для кандидатов; runtime `/start` и broadcast выбирают root по аудитории пользователя. Если подходящего меню нет, `/start` оставляет только приветствие без системного fallback-текста.

## Исследования

| Token | Статус | Название | Описание |
| --- | --- | --- | --- |
| `HRB-DISC-01` | `todo` | Способ идентификации текущих сотрудников в боте | Выбрать продуктовый механизм привязки сотрудника, который не проходил подбор через бота. |
| `HRB-DISC-02` | `todo` | Перевод кандидата в сотрудника | Спроектировать явный переход состояния и смену интерфейса бота после найма. |
| `HRB-DISC-03` | `todo` | Scope и auth для Telegram Mini Apps | Определить первый mini app, Telegram identity/auth модель, API boundaries и rollout после отпусков. |
| `HRB-DISC-04` | `todo` | Разделение данных для двух ИП | Подтвердить legal/data requirement и выбрать модель изоляции: две БД, два deployment-контура или другая схема с жестким разделением данных. |
| `HRB-DISC-05` | `todo` | Модель ролей и доступа админки | Выбрать целевую модель аккаунтов для HR, директора и технического администратора: роли, права на управление аккаунтами, аудит действий, session hardening и границы доступа к настройкам. |

## P2

| Token | Статус | Название | Описание |
| --- | --- | --- | --- |
| `HRB-P2-01` | `todo` | Признак руководителя и аудитории руководителей | Добавить флаг в карточку и использовать его в сценариях и массовых отправках. |
| `HRB-P2-02` | `todo` | Массовые действия по нескольким выбранным сотрудникам | Поддержать мультивыбор конкретных получателей. |
| `HRB-P2-03` | `todo` | Валидации пользовательского ввода | Формализовать и внедрить правила для ФИО, дат, файлов и других типов ответа. |
| `HRB-P2-04` | `doing` | Календарь и типизированные ответы в боте | Для scenario steps добавлен `response_type=date`: runtime показывает inline-календарь, workspace editor разрешает выбрать этот тип и сохранить результат в `first_workday`. Scheduler для time-based сценариев догоняет первый непройденный шаг в день активации, если его время уже прошло, не дублирует следующий `specific_time` шаг через internal follow-up и финально валидирует scheduled delivery перед отправкой, чтобы stale jobs после смены stage/scope не попадали в чат. Оставшийся scope: расширить date-target fields при реальной потребности и добавить более богатую валидацию дат. |
| `HRB-P2-05` | `doing` | UX-функции конструктора | `Назад` в runtime бота теперь уже не только навигационный: помимо `scenario_progress.step_history` используется отдельный undo-снимок последнего подтвержденного ответа, поэтому возврат откатывает последнее изменение карточки, `candidate_status`, survey answer и file upload, если они были созданы этим ответом. В React scenario workspace начат editor-side guardrail: тип ответа теперь явно помечает шаги, которые блокируют поток и ждут ответ пользователя; для `launch_scenario` disabled downstream select больше не притворяется активным при другом типе ответа. Дополнительно picker возврата из branch-step в root-flow теперь не держит невалидные значения и не предлагает текущий root-шаг ветвления, который backend все равно бы очистил при сохранении. Sidebar сценариев также получил явную сортировку (`недавно изменённые`, `сначала новые`, `сначала старые`, `по алфавиту`) вместо неочевидного порядка. Backend также уже отдает `workspace.graph` как read-only contract для будущего режима схемы. Оставшийся scope: более явная визуализация flow и, если понадобится, multi-step undo для terminal/side-effect branches. |
| `HRB-P2-06` | `todo` | MVP отпусков | После закрытия текущей стабилизации спроектировать и реализовать заявки на отпуск: сотрудник, даты, тип, статус, согласование и базовые уведомления. |
| `HRB-P2-07` | `todo` | UI и хранение для двух ИП | После решения `HRB-DISC-04` реализовать раздельное хранение данных по ИП и отобразить текущий юридический контур в админке, массовых действиях, карточках и runbook. |
| `HRB-P2-08` | `doing` | Security/compliance layer | Первый auth-hardening slice сделан в коде: signed session cookie вместо raw account id, TTL cookie, базовый login rate limit и запрет слабых новых паролей в account management. Для stage admin принят deferred baseline: домен + HTTPS reverse proxy + закрытый публичный `:8000`, без VPN-only на первом шаге; см. [[decisions/stage-admin-https-baseline]]. Оставшийся scope: целевые роли, аудит, секреты, backup policy, защита файлов/персональных данных, реализация HTTPS/proxy на stage, CSRF и broader hardening. |

## Правило обновления

Когда задача меняет статус:

- сначала обновить этот файл;
- если изменился operational context, обновить [[project_state]];
- если принято реальное техническое или продуктовое решение, добавить dated note в стиле [[decisions/obsidian-vault-adoption]].
- Obsidian Kanban, Canvas и Graph не являются каноническим backlog или architecture source; они могут быть только view/navigation поверх Markdown docs.
