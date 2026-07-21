---
title: Staff Telegram linking via work email OTP
date: 2026-07-21
status: accepted
doc_type: decision
area: bot-identity
related:
  - "../features/bot-identity.md"
  - "../backlog.md"
  - "../project_state.md"
---

# Staff Telegram linking via work email OTP

## Context

После отключения unsafe auto-creation бот больше не должен сам создавать карточки по неизвестному `/start`.
Но это оставило нерешенным главный реальный кейс: как штатному сотруднику впервые привязать свой Telegram к уже существующей карточке.

Привязка только по `telegram_username` слишком слабая:

- username в Telegram публичный и изменяемый;
- HR может знать username сотрудника заранее, но это не равно подтвержденной личности;
- такой же механизм нельзя безопасно использовать как единственный gate для штатного доступа.

Одновременно нельзя снова открывать свободную саморегистрацию кандидатов, потому что это возвращает мусорные карточки и плохой data hygiene.

## Decision

Принять двухконтурную модель:

1. Для штатных сотрудников первичная привязка Telegram делается только через OTP на `Employee.work_email`.
2. Для сотрудников заранее сохраненный `telegram_username` используется только как hint, чтобы бот мог предложить отправить код на известную рабочую почту.
3. Для кандидатов неизвестный `/start` не создает карточку и не запускает self-registration.
4. Для кандидатов, уже созданных HR и заранее связанных по `telegram_username`, legacy username linking временно сохраняется как допустимый путь.

## Consequences

### Плюсы

- У штатного сотрудника появляется реальный controlled linking flow без ручной помощи разработчика.
- `telegram_username` перестает быть единственной identity-опорой для staff access.
- Кандидатский flow не открывает новые мусорные записи.

### Минусы

- Появляется SMTP-зависимость и новый operational слой доставки OTP.
- Нужна поддержка pre-auth state machine (`employee_link_sessions`) поверх обычного bot runtime.
- Product-модель для invite flow кандидатов остается отдельной задачей, а не решается этим решением.

## Rejected alternatives

### Автопривязка сотрудника только по username

Отклонено как слишком слабая идентификация для staff-only сценариев и будущих mini-app / documents / internal menu actions.

### Возврат к полной self-registration кандидатов через `/start`

Отклонено, потому что это ломает качество данных и снова смешивает product flows кандидата и сотрудника.

### Отдельный бот для сотрудников и кандидатов

Отклонено на текущем этапе как лишнее удвоение конфигурации, контента и operational surface. Сначала нужен нормальный access-layer внутри одного бота.
