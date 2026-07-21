---
title: Email OTP bot linking handoff
date: 2026-07-21
status: active
doc_type: handoff
area: bot-identity
related:
  - "../features/bot-identity.md"
  - "../decisions/2026-07-21-staff-telegram-email-otp-linking.md"
  - "../backlog.md"
---

# Email OTP bot linking handoff

## Что сделано

- Для штатных сотрудников добавлен pre-auth linking flow в Telegram через OTP на `Employee.work_email`.
- Unknown users больше не регистрируются автоматически; бот показывает entry menu `Я сотрудник` / `Я кандидат`.
- Username-only match для staff больше не приводит к автопривязке: username используется только как hint, чтобы предложить отправку кода на уже известную рабочую почту.
- Legacy username linking для кандидатов, заранее созданных HR, сохранен.
- Для pre-auth state добавлена отдельная таблица `employee_link_sessions`.
- В employee record добавлены `telegram_verified_at` и `telegram_link_method`.

## Что важно интегратору

- Этот slice не деплоился на stage в рамках текущей ветки.
- Для живой работы на стенде нужны SMTP env-переменные; без них staff OTP flow не пройдет полный путь.
- В рабочем дереве есть unrelated dirty changes, особенно по frontend/static bundles и соседним backend-файлам. Их нельзя автоматически включать в merge только потому, что они рядом лежат.

## Что проверить при интеграции

1. У stage/env реально заполнены `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`.
2. У тестового сотрудника есть `work_email`.
3. `/start` для уже привязанного пользователя не уводит в pre-auth.
4. `/start` для username-only staff user предлагает OTP, а не привязывает аккаунт молча.
5. `/start` для username-only candidate user по-прежнему может подцепить заранее созданную карточку.

## Следующий логичный шаг

- Не плодить новый “умный” вопрос в стартовом сценарии про роль пользователя.
- Отдельно спроектировать invite/self-service flow для новых кандидатов.
- Отдельно решить lifecycle contract `candidate -> staff`, чтобы бот не смешивал две модели доступа в одном onboarding path.
