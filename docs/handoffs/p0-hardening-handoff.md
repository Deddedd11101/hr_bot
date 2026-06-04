---
title: Передача контекста по P0 hardening
date: 2026-05-08
status: active
task_tokens:
  - HRB-P0-01
  - HRB-P0-02
  - HRB-P0-03
  - HRB-P0-04
  - HRB-P0-05
  - HRB-P0-06
---

# Передача контекста по P0 hardening

## Что сделано

- Закрыта вся P0 wave:
  - unknown Telegram users больше не auto-create candidate records;
  - blocked employees отсекаются через `is_bot_blocked`;
  - stray text от known users игнорируется без service-noise replies;
  - inbound photo handling добавлен рядом с documents;
  - mass targeting теперь split employee и candidate stages;
  - shared card fields теперь consistently persist из обеих admin surfaces.
- Добавлено regression coverage для:
  - shared field persistence;
  - blocked launch refusal;
  - safe unknown-user behavior;
  - split mass targeting;
  - inbound file save rules.

## С чего начинать следующую работу

1. Прочитать [[project_state]].
2. Взять следующую задачу из [[backlog]], начиная с P1.
3. Если задача трогает transitions или identity, сначала прочитать [[features/bot-identity]] и [[features/employee-lifecycle]].

## Самая важная открытая работа

- `HRB-P1-01` status-triggered scenario launches.
- `HRB-P1-02` scenario transition semantics в новом admin.
- `HRB-P1-03` notification unification.
- `HRB-P1-06` scenario workspace performance pass.
- `HRB-DISC-01` final identity-linking product model.

## Риски

- `is_bot_blocked` — guardrail, а не full lifecycle model.
- Classic и React admin cards должны оставаться behaviorally aligned.
- Workspace performance problem все еще реальна и теперь заметнее, потому что P0 runtime bugs снижены.
