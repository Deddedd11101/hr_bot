---
title: Карта web-поверхности HR Bot
date: 2026-05-14
status: active
doc_type: feature
area: backend
task_tokens:
  - HRB-DOC-02
  - HRB-P1-07
related:
  - "[[api]]"
  - "[[architecture]]"
  - "[[lld/classic-to-react-admin-migration]]"
source_of_truth: true
---

# Карта web-поверхности

## Назначение

Документ описывает non-JSON HTTP surface:

- server-rendered HTML pages;
- classic form handlers;
- download/export routes;
- redirects для операторов.

Подробные JSON contracts находятся в [[api]].

## Сессия и модель доступа

- Browser auth использует cookie `hr_admin_auth`.
- Без auth classic routes обычно делают `303` redirect на `/login`.
- Без auth JSON routes возвращают `401`; это описано в [[api]].
- Admin-only boundary есть для settings-related pages через `_require_admin()`. Большинство операторских страниц требует только authenticated account.

## Вход и маршруты сессии

| Method | Path | Surface | Примечания |
| --- | --- | --- | --- |
| `GET` | `/login` | HTML page | Login screen |
| `POST` | `/login` | Form action | Аутентифицирует admin account, ставит auth cookie и ведет на `/app/employees?list_kind=candidates` |
| `POST` | `/logout` | Form action | Очищает auth cookie |
| `GET` | `/` | Redirecting page | Основная operator landing page после auth; сейчас ведет на `/app/employees?list_kind=candidates` |

## Операторская поверхность сотрудников и кандидатов

| Method | Path | Surface | Примечания |
| --- | --- | --- | --- |
| `GET` | `/candidates` | Redirect route | Legacy operator entrypoint; теперь ведет на `/app/employees?list_kind=candidates` |
| `GET` | `/employees` | Redirect route | Legacy operator entrypoint; теперь ведет на `/app/employees` |
| `GET` | `/app/employees` | React bootstrap page | Default employee/candidate list; поддерживает query `list_kind=candidates` |
| `GET` | `/app/employees/{employee_id}` | React bootstrap page | Новый employee detail screen |
| `GET` | `/employees/{employee_id}/edit` | HTML page | Classic employee edit form |
| `POST` | `/employees` | Form action | Создать employee/candidate из classic UI |
| `POST` | `/employees/{employee_id}` | Form action | Обновить employee/candidate из classic UI |
| `POST` | `/employees/{employee_id}/delete` | Form action | Удалить employee/candidate |
| `POST` | `/employees/{employee_id}/launch` | Form action | Immediate scenario launch из classic UI |
| `POST` | `/employees/{employee_id}/schedule` | Form action | Создать scheduled scenario launch |
| `POST` | `/employees/{employee_id}/schedule/{launch_request_id}/delete` | Form action | Удалить scheduled launch |
| `POST` | `/employees/{employee_id}/files` | Multipart form action | Загрузить outbound employee file |
| `GET` | `/employees/{employee_id}/files/{file_id}/download` | Download route | Скачать employee file |
| `POST` | `/employees/{employee_id}/files/{file_id}/send` | Form action | Отправить stored file в Telegram |
| `POST` | `/employees/{employee_id}/document-links` | Form action | Создать или обновить offer link |
| `POST` | `/employees/{employee_id}/document-links/{link_id}/delete` | Form action | Удалить offer link |
| `POST` | `/employees/{employee_id}/profile-photo` | Multipart form action | Загрузить profile photo |
| `POST` | `/employees/{employee_id}/profile-photo/delete` | Form action | Удалить profile photo |
| `GET` | `/employees/{employee_id}/card-image` | Generated media route | Сгенерировать PNG карточки сотрудника |

## Массовые действия

| Method | Path | Surface | Примечания |
| --- | --- | --- | --- |
| `GET` | `/bulk-actions` | Redirect route | Legacy operator entrypoint; теперь ведет на `/app/bulk-actions` |
| `GET` | `/app/bulk-actions` | React bootstrap page | React bulk actions; default sidebar entry, classic `/bulk-actions` остается fallback |
| `POST` | `/bulk-actions/scenarios/schedule` | Form action | Запланировать mass scenario |
| `POST` | `/bulk-actions/surveys/schedule` | Form action | Запланировать mass survey |
| `POST` | `/bulk-actions/scenarios/launch` | Form action | Запустить mass scenario сразу |
| `POST` | `/bulk-actions/surveys/launch` | Form action | Запустить mass survey сразу |
| `POST` | `/bulk-actions/messages/schedule` | Form action | Запланировать mass free-text message |
| `POST` | `/bulk-actions/messages/send` | Form action | Отправить mass free-text message сразу |
| `POST` | `/bulk-actions/scenarios/{action_id}/delete` | Form action | Удалить one mass scenario action |
| `POST` | `/bulk-actions/messages/{action_id}/delete` | Form action | Удалить one mass message action |

## Операторская поверхность сценариев и опросов

| Method | Path | Surface | Примечания |
| --- | --- | --- | --- |
| `POST` | `/flows/reorder` | Form action | Reorder classic scenarios |
| `POST` | `/surveys/reorder` | Form action | Reorder classic surveys |
| `GET` | `/flows` | Redirect route | Legacy operator entrypoint; теперь ведет на `/app/flows/workspace-v2` |
| `GET` | `/surveys` | Redirect route | Legacy operator entrypoint; теперь ведет на `/app/surveys/workspace` |
| `POST` | `/flows` | Form action | Создать scenario |
| `POST` | `/surveys` | Form action | Создать survey |
| `GET` | `/flows/{scenario_id}` | HTML page | Classic scenario editor |
| `GET` | `/surveys/{scenario_id}` | HTML page | Classic survey editor |
| `POST` | `/flows/{scenario_id}` | Form action | Обновить classic scenario |
| `POST` | `/surveys/{scenario_id}` | Form action | Обновить classic survey |
| `POST` | `/flows/{scenario_id}/copy` | Form action | Скопировать scenario |
| `POST` | `/surveys/{scenario_id}/copy` | Form action | Скопировать survey |
| `POST` | `/flows/{scenario_id}/delete` | Form action | Удалить scenario |
| `POST` | `/surveys/{scenario_id}/delete` | Form action | Удалить survey |
| `GET` | `/surveys/{scenario_id}/export` | Export route | Export survey answers |
| `GET` | `/flows/steps/{step_id}/attachment` | Download route | Скачать step attachment |
| `POST` | `/flows/steps/{step_id}/attachment/delete` | Form action | Удалить step attachment |
| `GET` | `/app/flows/workspace` | Redirect route | Legacy redirect в React workspace |
| `GET` | `/app/flows/workspace-v2` | React bootstrap page | Текущий scenario workspace |
| `GET` | `/app/surveys/workspace` | React bootstrap page | React survey workspace; sidebar default для опросов, использует `/api/flows/workspace?kind=survey` |

## Настройки и админские аккаунты

| Method | Path | Surface | Примечания |
| --- | --- | --- | --- |
| `GET` | `/settings` | Redirect route | Legacy operator entrypoint; теперь ведет на `/app/settings` |
| `POST` | `/settings` | Form action | Обновить HR settings |
| `POST` | `/settings/menu-sets` | Form action | Создать menu set |
| `POST` | `/settings/menu-sets/{menu_set_id}` | Form action | Обновить menu set |
| `POST` | `/settings/menu-sets/{menu_set_id}/delete` | Form action | Удалить menu set |
| `POST` | `/settings/menu-sets/{menu_set_id}/buttons` | Form action | Создать menu button |
| `POST` | `/settings/menu-buttons/{button_id}` | Form action | Обновить menu button |
| `POST` | `/settings/menu-sets/{menu_set_id}/buttons/save` | Form action | Сохранить order/values кнопок menu set |
| `POST` | `/settings/menu-buttons/save-all` | Form action | Bulk-save menu buttons |
| `POST` | `/settings/menu-buttons/{button_id}/delete` | Form action | Удалить menu button |
| `POST` | `/accounts` | Form action | Создать admin account |
| `POST` | `/accounts/{account_id}` | Form action | Обновить admin account |
| `POST` | `/accounts/{account_id}/delete` | Form action | Удалить admin account |
| `GET` | `/app/settings` | React bootstrap page | React settings/accounts/menu sets; default sidebar entry, classic `/settings` остается fallback |

## Статические ассеты

| Method | Path | Surface | Примечания |
| --- | --- | --- | --- |
| `GET` | `/static/*` | Static file mount | FastAPI отдает CSS, JS и built frontend assets из `app/static` |

## Текущая критика

- HTTP surface все еще hybrid, но operator entrypoints уже не конкурируют напрямую: классические `/employees`, `/candidates`, `/bulk-actions`, `/flows`, `/surveys`, `/settings` теперь только redirect routes в React surfaces. Write/read fallback URLs и form handlers пока остаются, поэтому граница все еще не идеальна.
- Многие operator actions все еще form posts with redirects. Это сохраняет старый UI, но усложняет automated API reasoning и contract drift tracking.
- Surveys получили React workspace route `/app/surveys/workspace`, но classic `/surveys/*` пока остается fallback и держит export answers.
