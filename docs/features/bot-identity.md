---
title: Идентификация в боте
date: 2026-05-06
status: active
doc_type: feature
area: bot
task_tokens:
  - HRB-P0-01
  - HRB-P0-02
  - HRB-P0-03
  - HRB-P0-04
  - HRB-DISC-01
related:
  - "[[project_state]]"
  - "[[backlog]]"
source_of_truth: true
---

# Идентификация в боте

## Текущее поведение

Бот связывает Telegram user с employee record через messaging identity helpers в `app.messaging.identity` и `app.messaging.service`.

Usernames нормализуются одинаково перед сравнением и сохранением: `@Name`, `Name`, ` name ` и `name` считаются одним public handle и хранятся без `@`, в lower-case. Это применяется и к legacy `Employee.telegram_username`, и к `EmployeeMessengerAccount.external_username`.

Текущий flow:

1. Найти existing employee по active Telegram channel user ID. Numeric Telegram ID является главным надежным идентификатором.
2. Если active account найден, но его employee отсутствует, runtime не считает это валидной привязкой и безопасно repair'ит orphan account перед дальнейшим `/start`.
3. Если numeric ID не найден, попробовать normalized public Telegram username как fallback для первичной привязки.
4. Если normalized username совпал с несколькими актуальными карточками, бот не угадывает:
   - не создает новую карточку;
   - не привязывает Telegram;
   - пишет warning в logs;
   - отвечает нейтральным текстом “Не удалось автоматически привязать Telegram, обратитесь к HR”.
5. Если `/start` не нашел карточку ни по numeric Telegram ID, ни по public username, создать новую candidate-карточку:
   - `employee_stage = candidate`;
   - `candidate_work_stage = NULL` (`Не указан`);
   - `telegram_user_id = <numeric Telegram ID>`;
   - `telegram_username = <normalized public username>`, если он есть.
6. Если username matched existing candidate without numeric chat ID, `/start` привязывает numeric Telegram ID к этой карточке и считает это регистрацией кандидата.
7. Если username matched existing `staff` / `adaptation` / `ipr`, `/start` только привязывает numeric Telegram ID и не запускает candidate registration scenario.
8. Если employee record есть, но `is_bot_blocked = true`, запретить все bot interaction с коротким отказом и не перепривязывать Telegram identity.
9. Candidate registration scenario запускается только при первом candidate-linking/create event и только для сценария, который реально матчится по `employee_scope=candidates`.
10. Повторный `/start` не создает дубль, не перезапускает registration-сценарий и работает как возврат к root menu.
11. `/start` не отправляет отдельное техническое приветствие. Если стартует registration-сценарий, пользователь получает первый шаг сценария; если сценарий не стартует, runtime пытается показать доступное root menu.

Reset/delete contract:

- Operator reset bot linkage из карточки чистит legacy Telegram поля, active `EmployeeMessengerAccount` rows для employee, незавершенный scenario runtime progress где employee является context или recipient, pending launch requests, `current_menu_set_id` и `current_menu_path`. Completed progress остается audit/history и не удаляется reset'ом.
- Удаление карточки через operator API удаляет связанные messenger account rows, все progress rows где employee является context, и только незавершенный progress где employee является recipient. Completed recipient progress у других context-карточек сохраняется как audit/history, чтобы app-level delete path не стирал чужую завершенную историю.
- Schema-level FK/cascade для `employee_messenger_accounts.employee_id` пока не введен; это отдельный data-model debt, а не часть текущего runtime repair.

Чего runtime не делает:

- Не перепривязывает numeric Telegram ID к другой карточке, если он уже валидно связан с existing employee.
- Не создает нового кандидата при конфликте нескольких карточек с одним normalized username.
- Не дает blocked matched employee обойти блокировку через username fallback или новую candidate-карточку.
- Не реализует повторный вход кандидата после отказа/архива. Refusal/archive re-entry должен быть отдельным HR-действием, иначе старая отказная карточка может неявно перехватывать `/start`.

## Что изменилось в P0

- `/start`, text, file-like media (`document` / `photo` / `video` / `video_note`) и callback entrypoints теперь используют один inbound access resolution path.
- Unknown users по-прежнему не могут создавать `employee_files` и не открывают runtime access через stray text/file input, но `/start` теперь является осознанной candidate-entry точкой и может создать новую candidate-карточку.
- Known users все еще могут быть linked по сохраненному normalized public username, если пишут с нового Telegram ID и match однозначный.
- Duplicate normalized username теперь является fail-closed состоянием, а не поводом выбрать первую карточку или создать дубль.
- Active orphan messenger accounts больше не считаются валидной identity; `/start` repair'ит такие строки на runtime path без destructive stage cleanup.
- Registration-сценарий привязан к факту нового candidate-linking/create event, а не к scheduler interval или каждому повторному `/start`.
- Сервисный текст `Привет! Я HR-бот.` не является частью `/start` contract: приветствие должно жить в registration-сценарии или в тексте меню.
- Blocked users не могут открывать menu flows, отвечать на scenario steps, upload files или получать new launches через scheduler/manual start.
- Known stray text вне expected scenario response игнорируется без service noise.

## Текущее практическое использование

- Модель сознательно асимметрична:
  - кандидат может войти в бот впервые через `/start` и быть создан автоматически;
  - существующий сотрудник должен быть заранее известен по numeric ID или public username.
- Это interim model до отдельной employee-auth/email verification схемы.

## Нужное будущее направление

- Не расширять auto-create с `/start` на обычные text/file/callback события, иначе бот снова начнет плодить мусор от случайных входящих сообщений.
- Выбрать intentional linking flow для existing employees beyond username fallback.
- Решить, будет linking code-based, HR-approved или через другой verification path.
- Оформить отдельный re-entry flow для отказных/архивных кандидатов: новая попытка должна быть явным HR-действием, а не побочным эффектом `/start`.

## Связанная работа

- `HRB-P0-01` stop unsafe auto-creation
- `HRB-P0-02` enforce blocked access
- `HRB-P0-03` remove service noise for stray text
- `HRB-P0-04` keep inbound media handling inside the same access model
- `HRB-DISC-01` choose the long-term employee identity model
