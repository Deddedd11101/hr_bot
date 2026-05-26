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
| `HRB-P1-01` | `todo` | Запуск сценария по смене HR-статуса | Стартовать сценарии при изменении статуса HR в админке. |
| `HRB-P1-02` | `todo` | Нормальная семантика перехода к другому сценарию | Отвязать переход к сценарию от искусственного `response_type`. |
| `HRB-P1-03` | `todo` | Унификация уведомлений | Свести общие, шаговые и button-based уведомления к одной модели. |
| `HRB-P1-04` | `todo` | Убрать пустые и системные сообщения из сценариев | Не отправлять пустые шаги и убрать служебные утечки в диалог. |
| `HRB-P1-05` | `todo` | Аудит доступности сценариев для ручного запуска | Проверить, почему новые сценарии не всегда видны в карточке сотрудника/кандидата. |
| `HRB-P1-06` | `todo` | Performance-pass новой админки сценариев | Уменьшить лаги конструктора без полного редизайна. |
| `HRB-P1-07` | `doing` | Перенос classic admin UI на React default | LLD зафиксирован; React default entry включен; `/app/settings`, `/app/bulk-actions` и `/app/surveys/workspace` реализованы. Неудачный эксперимент с `/app/ui-kit` удален из runtime: он не помог упростить создание страниц и только добавил лишнюю поверхность поддержки. В `frontend` инициализирован shadcn `components.json`, догружен расширенный набор `ui/*` компонентов, добавлен локальный `time-picker`; текущий стек фактически Base UI first, но часть legacy wrappers еще Radix. Основные React operator pages больше не живут как жирные entrypoints: `frontend/src/employees-list/` переведен на `bootstrap + page + local components + data + types`, `frontend/src/scenario-workspace/` разрезан на `main.tsx + page.tsx + model.ts + pickers.tsx + sections.tsx + types.ts`, `employee detail` перенесен в Vite bundle `frontend/src/employee-detail/` и разрезан на `main.tsx + page.tsx + sections.tsx + helpers.ts`, `frontend/src/bulk-actions/` и `frontend/src/settings/` тоже переведены на bootstrap/page split. Старые `app/static/react_employee_edit_*` удалены из runtime и репозитория; destructive actions приведены к реальному shared `Button` API (`destructive`, не `danger`). React templates вынесены с legacy `base.html` на отдельный `react_base.html` и `app/static/react_shell.css`, чтобы новые страницы больше не наследовали `app/static/styles.css`. Для route cleanup добавлен parity smoke в `tests/test_employee_api_smoke.py`: он покрывает employee detail writes, bulk-actions preview/schedule, settings workspace mutations и редиректы legacy operator entrypoints. Для backend cleanup начата безопасная декомпозиция `app/main.py`: reusable auth/render/access helpers вынесены в `app/web/support.py`, employee support/model helpers — в `app/web/employees.py`, employee React/API routes и classic employee tails — в `app/web/employee_routes.py`, bulk-actions targeting/workspace helpers и React/API routes плюс classic bulk tails — в `app/web/bulk_actions.py` и `app/web/bulk_action_routes.py`, settings workspace/helpers и React/API routes — в `app/web/settings.py` и `app/web/settings_routes.py`, а scenario/surveys React/API workspace helpers и routes — в `app/web/scenarios.py` и `app/web/scenario_routes.py`. Следующий шаг: не плодить новые workspace slices, а убирать classic settings form handlers, classic scenario/survey editor routes и remaining fallback URLs после отдельного parity/cleanup прохода. |

## Исследования

| Token | Статус | Название | Описание |
| --- | --- | --- | --- |
| `HRB-DISC-01` | `todo` | Способ идентификации текущих сотрудников в боте | Выбрать продуктовый механизм привязки сотрудника, который не проходил подбор через бота. |
| `HRB-DISC-02` | `todo` | Перевод кандидата в сотрудника | Спроектировать явный переход состояния и смену интерфейса бота после найма. |
| `HRB-DISC-03` | `todo` | Scope и auth для Telegram Mini Apps | Определить первый mini app, Telegram identity/auth модель, API boundaries и rollout после отпусков. |
| `HRB-DISC-04` | `todo` | Разделение данных для двух ИП | Подтвердить legal/data requirement и выбрать модель изоляции: две БД, два deployment-контура или другая схема с жестким разделением данных. |

## P2

| Token | Статус | Название | Описание |
| --- | --- | --- | --- |
| `HRB-P2-01` | `todo` | Признак руководителя и аудитории руководителей | Добавить флаг в карточку и использовать его в сценариях и массовых отправках. |
| `HRB-P2-02` | `todo` | Массовые действия по нескольким выбранным сотрудникам | Поддержать мультивыбор конкретных получателей. |
| `HRB-P2-03` | `todo` | Валидации пользовательского ввода | Формализовать и внедрить правила для ФИО, дат, файлов и других типов ответа. |
| `HRB-P2-04` | `todo` | Календарь и типизированные ответы в боте | Убрать свободный текст там, где нужен контролируемый ввод даты. |
| `HRB-P2-05` | `todo` | UX-функции конструктора | Фильтры, редактирование названия, выгрузка текстов, блок-схема, drag между сценариями и шаг назад. |
| `HRB-P2-06` | `todo` | MVP отпусков | После закрытия текущей стабилизации спроектировать и реализовать заявки на отпуск: сотрудник, даты, тип, статус, согласование и базовые уведомления. |
| `HRB-P2-07` | `todo` | UI и хранение для двух ИП | После решения `HRB-DISC-04` реализовать раздельное хранение данных по ИП и отобразить текущий юридический контур в админке, массовых действиях, карточках и runbook. |
| `HRB-P2-08` | `todo` | Security/compliance layer | После стабилизации основных модулей провести security hardening: роли, аудит, секреты, backup policy, защита файлов/персональных данных, session/cookie/CSRF/rate-limit checks. |

## Правило обновления

Когда задача меняет статус:

- сначала обновить этот файл;
- если изменился operational context, обновить [[project_state]];
- если принято реальное техническое или продуктовое решение, добавить dated note в стиле [[decisions/obsidian-vault-adoption]].
- Obsidian Kanban, Canvas и Graph не являются каноническим backlog или architecture source; они могут быть только view/navigation поверх Markdown docs.
