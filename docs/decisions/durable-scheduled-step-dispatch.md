---
title: Сохранённая доставка старых плановых шагов
date: 2026-11-10
status: accepted
doc_type: adr
area: bot
related:
  - "[[features/scenario-engine]]"
  - "[[data-model]]"
  - "[[stage-deploy]]"
source_of_truth: true
---

## Решение

APScheduler больше не является единственным хранилищем legacy timed step jobs.
Новые задания сохраняются в SQLite ledger до processed handoff исходного запроса.
Scheduler scan и memory callback используют один conditional claim и общий
recipient admission. Тайминги остаются прежними, но нормализуются в UTC.

Batch и progress id/started_at отделяют независимые запуски от продолжений.
OnboardingEvent получает nullable scenario/batch attribution; auto-follow не
порождает повторную отправку тем же таймером. Ожидание человека не имеет срока.
Starting — не истекающая lease: после неизвестного I/O нужна проверка, не replay.

Немедленная массовая отправка сохраняет recipient snapshot до первой попытки,
используя уже существующий ledger. Не создаём ещё один механизм хранения ответов:
survey launch IDs, XLSX и прежняя история сохраняются.

## Границы

Новая таблица не восстанавливает потерянные до обновления memory jobs.
Старым событиям не приписываются вымышленные batch IDs. Это не обещание
exactly-once внешней Telegram доставки и не единая FIFO всех источников.
Pending root отменяется явно; continuation останавливается прерыванием своего
диалога, а starting/failed сохраняются для ручной диагностики. Rollback требует
знания ledger, удаления таблиц как способа отката нет.
