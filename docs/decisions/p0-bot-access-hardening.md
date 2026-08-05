---
title: P0-ужесточение доступа к боту
date: 2026-05-08
status: accepted
doc_type: adr
area: bot
task_tokens:
  - HRB-P0-01
  - HRB-P0-02
  - HRB-P0-03
  - HRB-P0-04
  - HRB-P0-05
  - HRB-P0-06
related:
  - "[[features/bot-identity]]"
  - "[[backlog]]"
source_of_truth: true
---

# P0-ужесточение доступа к боту

Реализовать P0 bot hardening с safe-by-default моделью: неизвестные Telegram users не создают records, blocked employees отсекаются на ingress, а mass targeting разделяется между employee stages и candidate stages.

## Контекст

- Предыдущий bot identity path молча создавал candidate rows для неизвестных Telegram users.
- У bot access не было enforced termination/block state.
- Mass actions смешивали candidate и employee targeting в одном legacy `target_statuses` field.
- Shared employee card fields фактически не были shared в update logic.

## Выбранная модель

- Использовать один inbound access resolution path для `/start`, text, file, photo и callback events.
- Для unknown users возвращать короткую инструкцию вместо создания данных.
- Для blocked users enforce один boolean `is_bot_blocked` across bot runtime, scheduler и manual launches.
- Разделить mass targeting на:
  - `target_employee_stages`;
  - `target_candidate_stages`.
- Продолжать читать legacy `target_statuses`, чтобы older rows still resolve.

## Последствия

### Плюсы

- Бот больше не загрязняет базу guessed identities.
- HR может сразу остановить bot access из карточки сотрудника.
- Candidate и employee audience targeting теперь соответствуют реальной data model.
- Shared employee card fields обновляются consistently в classic и React surfaces.

### Компромиссы

- Unknown employees, которые никогда не были linked, все еще требуют отдельного product flow перед использованием бота.
- `is_bot_blocked` намеренно минимален и еще не является full employment-state model.
- Legacy mass action rows все еще несут старую semantics и должны интерпретироваться, а не rewrite in place.

## Следующие шаги

- Long-term linking design держать в [[features/bot-identity]] под `HRB-DISC-01`.
- Candidate-to-employee promotion design держать в [[features/employee-lifecycle]] под `HRB-DISC-02`.
- Следующий execution priority — P1 и performance cleanup в [[backlog]].
