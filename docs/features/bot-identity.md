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
3. Если все еще не найден, не создавать record и вернуть короткую инструкцию обратиться в HR.
4. Если employee record есть, но `is_bot_blocked = true`, запретить все bot interaction с коротким отказом.
5. Если `/start` впервые привязал numeric Telegram chat ID к карточке, сразу запускается первый подходящий scenario с `trigger_mode=bot_registration`.
6. Повторный `/start` не перезапускает registration-сценарий и работает как возврат к root menu.

## Что изменилось в P0

- `/start`, text, file, photo и callback entrypoints теперь используют один inbound access resolution path.
- Unknown users больше не создают `employees` rows или `employee_files`.
- Known users все еще могут быть linked по сохраненному public username, если пишут с нового Telegram ID.
- Registration-сценарий привязан к факту новой Telegram-привязки, а не к scheduler interval или каждому повторному `/start`.
- Blocked users не могут открывать menu flows, отвечать на scenario steps, upload files или получать new launches через scheduler/manual start.
- Known stray text вне expected scenario response игнорируется без service noise.

## Текущее практическое использование

- Safe by default для текущего production-like использования.
- Это все еще не финальная identity product model для existing employees, которые раньше не были linked.

## Нужное будущее направление

- Оставить unknown-user behavior non-destructive.
- Выбрать intentional linking flow для existing employees.
- Решить, будет linking code-based, HR-approved или через другой verification path.

## Связанная работа

- `HRB-P0-01` stop unsafe auto-creation
- `HRB-P0-02` enforce blocked access
- `HRB-P0-03` remove service noise for stray text
- `HRB-P0-04` keep inbound media handling inside the same access model
- `HRB-DISC-01` choose the long-term employee identity model
