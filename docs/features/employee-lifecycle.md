---
title: Жизненный цикл сотрудника
date: 2026-05-06
status: active
task_tokens:
  - HRB-DISC-02
  - HRB-P0-02
  - HRB-P1-01
---

# Жизненный цикл сотрудника

## Текущая модель

Система сейчас хранит кандидатов и сотрудников в одной таблице `employees`.

Практический split кодируется через поля:

- `employee_stage`
- `candidate_work_stage`
- `candidate_status`

## Что уже есть

- Candidate records можно создавать вручную в admin.
- Employee records редактируются из той же shared data model.
- Scenarios могут target `all`, `employees` или `candidates`.
- Onboarding scenarios уже есть для реальных employees.
- Recruitment flow уже есть для candidates.
- Employee records теперь включают `is_bot_blocked` как enforced runtime control для bot access.
- HR-статус кандидата в карточке теперь нормализован под явный shortlist:
  - `company_decline` — Наш отказ
  - `hr_interview` — Собеседование с HR
  - `manager_interview` — Собеседование с руководителем
  - `testing` — Тестирование
  - `offer` — Оффер
  - `preonboarding` — Преонбординг
  - `candidate_decline` — Отказ кандидата
- Сценарии теперь могут подписываться на смену HR-статуса кандидата через `trigger_mode=candidate_hr_stage` и `candidate_work_stage_trigger=<status>`.

## Чего не хватает

- Нет явного controlled transition “candidate becomes employee”.
- Нет устойчивой модели переключения bot UI из candidate behavior в employee menu behavior.
- Полной trigger matrix из HR status changes в scenario launches все еще нет: сейчас есть только direct launch по change event без richer event policy, cooldown и dedupe за пределами одного фактического изменения статуса.

## Важное следствие

Shared table упрощает implementation, а `is_bot_blocked` дает минимальный lifecycle safety brake. Но transition semantics все еще underspecified: blocked employee не равен properly modeled terminated employee, а candidate пока не promoted через explicit controlled transition.

## Связанная работа

- `HRB-DISC-02` define candidate-to-employee transition
- `HRB-P0-02` add blocked/terminated employee handling
- `HRB-P1-01` launch scenarios from HR status transitions
