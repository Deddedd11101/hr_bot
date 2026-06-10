---
title: Явный HR-cutover кандидата в адаптацию
date: 2026-06-09
status: accepted
doc_type: decision
area: employee-lifecycle
related:
  - "[[project_state]]"
  - "[[architecture]]"
  - "[[api]]"
  - "[[handoffs/frontend-structure-reset-handoff]]"
source_of_truth: true
---

# Контекст

После расширения React employee detail встал продуктовый вопрос: что делать, когда кандидат принял оффер. Прямой auto-convert из ответа в Telegram выглядел слишком рискованно:

- `offer accepted` не равен `сотрудник реально вышел в адаптацию`;
- между согласием и реальным стартом могут быть документы, подтверждение даты выхода и отдельное HR-решение;
- автоматический перевод в `staff` был бы еще слабее и создавал бы ложные кадровые переходы.

# Решение

Принят первый безопасный срез:

- переход делается **явным HR-действием** из карточки кандидата;
- первая целевая стадия — **`adaptation`**, не `staff`;
- в backend добавлен `POST /api/employees/{employee_id}/promote-to-adaptation`;
- переход разрешен только если:
  - сотрудник все еще находится в `employee_stage == "candidate"`;
  - у карточки уже указан `first_workday`;
- при переходе:
  - `candidate_work_stage` очищается;
  - `adaptation_midpoint` и `adaptation_end` заполняются от `first_workday`, если оператор еще не ввел явные даты;
  - `current_menu_set_id` сбрасывается, чтобы после перехода пересчитать menu/audience как для employee/adaptation-состояния.

# Последствия

- HR получил безопасный и прозрачный lifecycle cutover без скрытой автоматизации.
- Product boundary стала честнее: согласие на оффер пока не запускает автоперевод, и это требует отдельного решения.
- Следующий вопрос уже не про кнопку перехода, а про lifecycle semantics:
  - нужен ли отдельный статус/событие `offer accepted`;
  - какие сценарии, если вообще какие-то, должны автоматически стартовать от перехода в `adaptation`.
