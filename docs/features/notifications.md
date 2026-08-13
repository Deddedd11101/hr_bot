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
- Используются для широких событий вроде завершения сценария и получения тестового задания.
- Исполняются через `app.notifications`.

### Уведомления на уровне шага

- Новая множественная модель хранится в `step_send_notifications`.
- Legacy `notify_on_send_*` поля в `flow_step_templates` остаются compatibility seam, но не должны считаться целевой product-моделью.
- Уведомление может отправлять текст, когда шаг показан пользователю.
- Targeting получателей для новых scenario notification rules теперь role-only: `hr`, `manager`, `mentor_adaptation`, `mentor_ipr`.
- `hr` резолвится через `HrSettings.telegram_user_id`.
- `manager` / `mentor_adaptation` / `mentor_ipr` резолвятся через relation-поля карточки сотрудника и их primary Telegram chat id.
- Если роль не может быть резолвлена в chat id, уведомление просто пропускается и не валит отправку шага или кнопочного ответа.
- Legacy `employee:{id}` допускается только как runtime compatibility seam для уже существующих строк БД; новые UI/API payloads не должны его сохранять.

### Уведомления на уровне кнопки

- Хранятся в `step_button_notifications`.
- Срабатывают только при выборе конкретного варианта кнопки.

## Текущие проблемы

- Модель разделена между несколькими storage и execution paths.
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
