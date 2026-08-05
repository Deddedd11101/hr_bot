---
title: Жизненный цикл сотрудника
date: 2026-05-06
status: active
doc_type: feature
area: product
task_tokens:
  - HRB-DISC-02
  - HRB-P0-02
  - HRB-P1-01
related:
  - "[[project_state]]"
  - "[[backlog]]"
  - "[[decisions/2026-06-09-candidate-to-adaptation-cutover]]"
  - "[[decisions/2026-07-21-manager-assignment-trigger]]"
source_of_truth: true
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
- React employee detail уже имеет явный HR cutover `candidate -> adaptation`: оператор должен задать `first_workday`, после чего система очищает candidate-only stage и seed-ит adaptation dates.
- При назначении руководителя сотруднику в `adaptation` backend может создать trigger launch request для сценария `manager_assigned_adaptation`.

## Чего не хватает

- Нет устойчивой модели переключения bot UI из candidate behavior в employee menu behavior.
- Нет полной trigger matrix из HR status changes и assignment events в scenario launches.
- Нет product-решения, должен ли bot-driven `offer accepted` создавать отдельный статус/событие до HR cutover.

## Важное следствие

Shared table упрощает implementation, а `is_bot_blocked` дает минимальный lifecycle safety brake. Но transition semantics все еще underspecified: blocked employee не равен properly modeled terminated employee, а explicit HR cutover в `adaptation` не заменяет полную lifecycle/event модель.

## Связанная работа

- `HRB-DISC-02` define candidate-to-employee transition
- `HRB-P0-02` add blocked/terminated employee handling
- `HRB-P1-01` launch scenarios from HR status transitions
