---
title: Уведомления
date: 2026-05-06
status: active
doc_type: feature
area: bot
task_tokens:
  - HRB-P1-03
related:
  - "[[project_state]]"
  - "[[backlog]]"
  - "[[decisions/2026-06-04-notification-scope-boundary]]"
source_of_truth: true
---

# Уведомления

## Текущие слои уведомлений

### Глобальные HR-уведомления

- Хранятся в `hr_settings`.
- Используются для несценарных/system events, например получения тестового задания или отдельных user actions.
- Исполняются через `app.notifications`.
- Legacy flag `notify_scenario_completed` остается в `hr_settings` для совместимости, но scenario runtime больше не отправляет Telegram-сообщения о прохождении шага/этапа с техническими `scenario_key` / `step_key`.
- Технические ключи сценариев и шагов допустимы только в logs/audit, не в пользовательских Telegram-уведомлениях.
- `telegram_user_id` — основной HR Telegram для role token `hr`.
- `notification_recipient_ids` — legacy/additional recipients для глобальных `app.notifications` events; scenario notification rules не используют этот список как расширение `hr`.

### Уведомления на уровне шага

- Новая множественная модель хранится в `step_send_notifications`.
- Legacy `notify_on_send_*` поля в `flow_step_templates` остаются compatibility seam, но не должны считаться целевой product-моделью.
- Уведомление может отправлять текст, когда шаг показан пользователю.
- Targeting получателей для новых scenario notification rules теперь role-only: `hr`, `manager`, `mentor_adaptation`, `mentor_ipr`.
- `hr` резолвится через `HrSettings.telegram_user_id`.
- `manager` / `mentor_adaptation` / `mentor_ipr` резолвятся через relation-поля карточки сотрудника и их primary Telegram chat id.
- Если роль не может быть резолвлена в chat id, уведомление просто пропускается и не валит отправку шага или кнопочного ответа.
- Legacy `employee:{id}` допускается только как runtime compatibility seam для уже существующих строк БД; новые UI/API payloads не должны его сохранять.
- Raw chat ids и произвольные recipient ids в scenario notification rules не резолвятся runtime-ом и должны отбрасываться на save.

### Уведомления на уровне кнопки

- Хранятся в `step_button_notifications`.
- Срабатывают только при выборе конкретного варианта кнопки.
- Используют тот же role-only recipient contract, что и уведомления на уровне шага.

## Текущие проблемы

- Модель все еще разделена между несколькими storage и execution paths.
- Новый React workspace уже закрыл часть classic-only gaps для button и step-level notifications, но legacy compatibility поля еще остаются в модели.
- Текущие уведомления в основном text-oriented и пока не выражают “отправить присланный файл или ссылку” как first-class behavior.
- Tagging и template capabilities неполны с бизнес-точки зрения.

## Желаемое направление

Нужна одна понятная модель:

- когда срабатывает уведомление;
- кто получает уведомление;
- какой user payload прикладывается;
- какие variables и tags доступны.

## Связанная работа

- `HRB-P1-03` унифицировать и нормализовать уведомления across step и button flows.
