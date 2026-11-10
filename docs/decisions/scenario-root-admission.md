---
title: Транзакционный допуск root-сценариев
date: 2026-11-10
status: accepted
doc_type: adr
area: bot
related:
  - "[[features/scenario-engine]]"
  - "[[data-model]]"
source_of_truth: true
---

## Решение

Для root-вызовов start_scenario используем существующий ScenarioProgress как
durable reservation. Admission и reset/первый snapshot выполняются под SQLite
writer lock, полученным через no-op UPDATE subject/recipient employees.
Перед Telegram I/O lock освобождается commit-ом с уже видимым progress.
Новая lease/outbox таблица на этом этапе не вводится.

## Почему

Отдельные claims источников защищают только один request/recipient row, но не
общий диалог web/worker. Python Lock не работает между процессами. Повторная
проверка progress под DB writer lock закрывает race для общего root-входа без
миграции и без удаления старых диалогов. Между claim источника и допуском может
выиграть другой запуск; это отдельный pre-I/O результат, не ошибка Telegram.

## Последствия и границы

- Active/waiting/неопределённый progress не истекает автоматически. Завершение
  или безопасное явное прерывание остаётся обычным способом освобождения.
- Durable sources сохраняют очередь при ScenarioRecipientBusy; после реального
  I/O сбоя прежняя консервативная starting/reservation защита не ослабляется.
- First delivery фиксирует адресата, повторно проверяя его привязку перед I/O.
- Гарантия проверяется для deployed SQLite. Это не заявление о совместимости
  уровней изоляции всех возможных SQL backends.
- Прямые send_step jobs, очередь шагов/продолжений, HR-only recipient без employee
  и общая FIFO всех источников требуют последующих отдельных решений. Нельзя
  выдавать root admission за завершённый универсальный delivery dispatcher.
