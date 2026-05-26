---
title: Safe extraction of main.py support layer
date: 2026-05-26
status: accepted
doc_type: decision
area: backend
task_tokens:
  - HRB-P1-07
related:
  - "[[architecture]]"
  - "[[project_state]]"
  - "[[handoffs/frontend-structure-reset-handoff]]"
source_of_truth: true
---

# Контекст

`app/main.py` разросся до монолитного FastAPI composition root: в нем смешаны auth/session helpers, template rendering, classic HTML routes, React entrypoints и JSON API. Пока этот файл остается единственной точкой даже для базовой web-обвязки, любой следующий route cleanup или backend refactor дает слишком широкий diff и плохо делится на чистые коммиты.

# Решение

Декомпозицию `app/main.py` начинать не с массового переноса роутов, а с безопасного support-layer extraction:

- reusable template rendering helpers;
- login redirect/auth guards;
- API/admin access guards.

Первый шаг выносится в `app/web/support.py` без изменения route behavior и без смены URL contracts.

# Почему так

- Это создает первый стабильный seam в backend-слое без параллельного переписывания 100+ route handlers.
- Такой перенос можно проверять существующим smoke (`tests/test_employee_api_smoke.py`), а не только визуально.
- После этого vertical slices (`employees`, `bulk-actions`, `settings`, `scenario/surveys`) уже можно выносить не из completely flat файла, а из модуля с хотя бы минимальной структурой.

# Последствия

- `app/main.py` пока остается большим, но больше не является единственным владельцем базовой web-support логики.
- Следующие шаги должны идти по тому же принципу: narrow extractions with green smoke, а не “распилим весь main.py за один проход”.
