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

Текущий flow:

1. Найти existing employee по Telegram channel user ID.
2. Если не найден, попробовать public Telegram username.
3. Если `/start` не нашел карточку ни по numeric Telegram ID, ни по public username, создать новую candidate-карточку:
   - `employee_stage = candidate`;
   - `candidate_work_stage = NULL` (`Не указан`);
   - `telegram_user_id = <numeric Telegram ID>`;
   - `telegram_username = <public username>`, если он есть.
4. Если username matched existing candidate without numeric chat ID, `/start` привязывает numeric Telegram ID к этой карточке и считает это регистрацией кандидата.
5. Если username matched existing `staff` / `adaptation` / `ipr`, `/start` только привязывает numeric Telegram ID и не запускает candidate registration scenario.
6. Если employee record есть, но `is_bot_blocked = true`, запретить все bot interaction с коротким отказом и не перепривязывать Telegram identity.
7. Candidate registration scenario запускается только при первом candidate-linking/create event и только для сценария, который реально матчится по `employee_scope=candidates`.
8. Повторный `/start` не создает дубль, не перезапускает registration-сценарий и работает как возврат к root menu.
9. `/start` не отправляет отдельное техническое приветствие. Если стартует registration-сценарий, пользователь получает первый шаг сценария; если сценарий не стартует, runtime пытается показать доступное root menu.

## Что изменилось в P0

- `/start`, text, file-like media (`document` / `photo` / `video` / `video_note`) и callback entrypoints теперь используют один inbound access resolution path.
- Unknown users по-прежнему не могут создавать `employee_files` и не открывают runtime access через stray text/file input, но `/start` теперь является осознанной candidate-entry точкой и может создать новую candidate-карточку.
- Known users все еще могут быть linked по сохраненному public username, если пишут с нового Telegram ID.
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

## Связанная работа

- `HRB-P0-01` stop unsafe auto-creation
- `HRB-P0-02` enforce blocked access
- `HRB-P0-03` remove service noise for stray text
- `HRB-P0-04` keep inbound media handling inside the same access model
- `HRB-DISC-01` choose the long-term employee identity model
