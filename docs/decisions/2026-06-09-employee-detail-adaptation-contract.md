---
title: Employee Detail Adaptation Contract
date: 2026-06-09
status: accepted
doc_type: adr
area: employee-detail
source_of_truth: true
---

# Контекст

В React employee detail реквизиты сопровождения сотрудника долгое время были либо placeholder-полями, либо сырыми строками `telegram_id`. Это было слабой моделью:

- оператор редактировал не сущность “руководитель/наставник”, а transport-level идентификатор;
- середина и конец адаптации в продуктовой логике просились как явные даты, но runtime считал их только расчетом от `first_workday`;
- UI выглядел как готовая функция, хотя data contract для нее был неполным.

# Решение

- Руководитель, наставник адаптации и наставник ИПР сохраняются как связи на сотрудников:
  - `manager_employee_id`
  - `mentor_adaptation_employee_id`
  - `mentor_ipr_employee_id`
- В карточке сотрудника добавлены явные adaptation-поля:
  - `adaptation_tasks_url`
  - `adaptation_feedback_url`
  - `adaptation_midpoint`
  - `adaptation_end`
- В React employee detail эти роли выбираются только из сотрудников со статусом `staff`.
- Scenario trigger modes:
  - `first_workday` продолжает опираться на `first_workday`
  - `mid_probation` сначала использует `adaptation_midpoint`, затем fallback к расчету от `first_workday`
  - `end_probation` сначала использует `adaptation_end`, затем fallback к расчету от `first_workday`

# Последствия

- Карточка сотрудника перестает редактировать transport-layer поля как source of truth.
- Existing notification/runtime flows не ломаются сразу, потому что legacy `*_telegram_id` продолжают синхронизироваться из выбранных staff employees.
- Следующий вопрос уже не про relation/date contract, а про продуктовую семантику adaptation artifacts:
  - достаточно ли URL-полей для задач/обратной связи
  - нужен ли отдельный `manager_position`
  - нужно ли переводить adaptation artifacts в first-class file uploads
