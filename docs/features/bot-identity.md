---
title: Идентификация в боте
date: 2026-05-06
status: active
task_tokens:
  - HRB-P0-01
  - HRB-P0-02
  - HRB-P0-03
  - HRB-P0-04
  - HRB-DISC-01
---

# Идентификация в боте

## Текущее поведение

Бот связывает Telegram user с employee record через `app.messaging.identity`, `app.messaging.service` и `app.messaging.verification`.

Базовый inbound flow теперь такой:

1. Найти existing employee по Telegram channel user ID.
2. Если user ID не найден, попробовать public Telegram username.
3. Если username совпал с кандидатом, разрешить безопасную legacy-привязку по username.
4. Если username совпал со штатным сотрудником, не привязывать автоматически: сначала потребовать подтверждение через рабочую почту и OTP.
5. Если match не найден, считать это новым кандидатом: создать candidate-card, привязать Telegram и сразу запустить candidate registration scenario.
6. Если employee record есть, но `is_bot_blocked = true`, запретить все bot interaction с коротким отказом.

## Новый product baseline

### 1. Сотрудник

- Сотрудник может быть привязан к Telegram только после проверки рабочей почты `work_email`.
- OTP отправляется на `Employee.work_email` через SMTP-настройки приложения.
- Если HR заранее заполнил `telegram_username`, это работает только как hint: бот может предложить отправить код на уже известную рабочую почту, но не связывает аккаунт автоматически.
- После успешной OTP-проверки бот сохраняет `telegram_user_id`, `telegram_username`, `telegram_verified_at` и `telegram_link_method=email_otp`.

### 2. Кандидат

- Кандидат может быть найден по заранее сохраненному `telegram_username`, если карточка уже была создана HR.
- Если бот не распознал пользователя как сотрудника и не нашел готовую карточку, `/start` создает новую candidate-card автоматически.
- После создания карточки бот сразу пытается запустить первый подходящий сценарий с `trigger_mode=bot_registration` и candidate-аудиторией.
- Эта модель допустима только потому, что бот не предполагается публичным каталогом: ссылку на него кандидат получает уже после контакта с HR.

### 3. Уже привязанный пользователь

- Если Telegram `chat_id` уже связан с карточкой, бот доверяет этому каналу как primary identity.
- `/start` для такого пользователя не должен повторно запускать pre-auth flow и не должен требовать OTP.

## Runtime детали

- Для pre-auth состояния используется таблица `employee_link_sessions`.
- Entry menu и OTP flow обрабатываются в `handle_start_command()` и `handle_text_event()` до обычного scenario/menu runtime.
- Candidate username match, candidate auto-create и staff email OTP intentionally различаются: это осознанное разделение, а не недоделка.
- При ручной привязке Telegram из админки карточка отмечается как `telegram_link_method=admin_manual`.
- Runtime по-прежнему умеет reclaim orphan messenger account, но не должен молча перепривязывать identity между живыми карточками.

## Настройки и зависимости

- Для staff OTP нужны SMTP-переменные окружения: host, port, credentials, sender и transport mode.
- TTL и retry policy OTP управляются отдельными env-настройками:
  - `TELEGRAM_LINK_OTP_TTL_MINUTES`
  - `TELEGRAM_LINK_OTP_MAX_ATTEMPTS`
  - `TELEGRAM_LINK_OTP_RESEND_COOLDOWN_SECONDS`

## Почему это лучше прежней модели

- Username в Telegram не является достаточной идентификацией для действующего сотрудника.
- Полная автогенерация для неизвестных пользователей все еще рискованна в публичном боте, но в текущем процессе это осознанный tradeoff: бот раздается HR точечно, а не индексируется как общедоступная форма.
- Один `/start` теперь разделен по real audience: распознанный staff идет в auth-flow, нераспознанный user трактуется как новый кандидат.

## Оставшиеся ограничения

- Если бот начнут распространять шире текущего HR-процесса, candidate auto-create снова станет спорным и потребует invite-gate.
- Это не решает product-модель перехода `candidate -> staff`; после оффера нужен отдельный lifecycle contract.
- SQLite-схема все еще не закрывает orphan messenger accounts на уровне foreign key/cascade.

## Связанная работа

- `HRB-P0-01` stop unsafe auto-creation
- `HRB-P0-02` enforce blocked access
- `HRB-P0-03` remove service noise for stray text
- `HRB-P0-04` keep inbound media handling inside the same access model
- `HRB-DISC-01` choose the long-term employee identity model
