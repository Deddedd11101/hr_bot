---
title: Передача контекста по принятию docs vault
date: 2026-05-06
status: active
task_tokens:
  - HRB-DOC-01
---

# Передача контекста по принятию docs vault

## Что сделано

- `docs/` принят как repository-backed documentation vault.
- Созданы live source-of-truth docs:
  - [[README]]
  - [[backlog]]
  - [[project_state]]
  - [[architecture]]
- Добавлены subsystem notes:
  - [[features/scenario-engine]]
  - [[features/notifications]]
  - [[features/employee-lifecycle]]
  - [[features/bot-identity]]
- Existing handoff documents перенесены в `docs/handoffs/`.
- Supporting documentation перенесена в `docs/features/`.
- Решение записано в [[decisions/obsidian-vault-adoption]].

## С чего начинать следующую работу

1. Прочитать [[project_state]].
2. Взять следующую execution task из [[backlog]].
3. Перед изменением подсистемы открыть relevant feature note.

## Самая важная открытая работа

- `HRB-P0-01` исправить unsafe bot identity auto-creation.
- `HRB-P0-02` добавить blocked/terminated employee mode.
- `HRB-P0-04` стабилизировать file/media intake из Telegram.
- `HRB-P0-05` исправить mass targeting model для candidates versus employees.
- `HRB-P0-06` воспроизвести и исправить card persistence issues across both admin surfaces.

## Риски

- Classic и React admin screens сосуществуют и должны оставаться behaviorally aligned.
- Current bot identity behavior все еще risky для real employee matching.
- Scenario workspace остается тяжелым; UX и performance issues реальны, не косметика.
