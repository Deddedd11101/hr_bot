---
title: main.py composition root cutover
date: 2026-05-26
status: accepted
doc_type: adr
area: backend
task_tokens:
  - HRB-P1-07
related:
  - "[[architecture]]"
  - "[[project_state]]"
  - "[[backlog]]"
source_of_truth: true
---

# Контекст

`app/main.py` разросся до многотысячного монолита, потому что в одном файле одновременно жили:

- startup и middleware;
- auth/session pages;
- classic HTML routes;
- React bootstrap routes;
- JSON API;
- helper-логика для employees, bulk-actions, settings и scenario/surveys.

Это делало почти любой backend diff слишком широким и мешало безопасно удалять старые поверхности.

# Решение

Принято довести `app/main.py` до composition-root роли и вынести operator route ownership в `app/web/*`.

Текущий контракт:

- `app/main.py` держит:
  - `FastAPI(...)`
  - static mount
  - middleware
  - login/logout/index pages
  - `include_router(...)`
- `app/web/support.py` держит auth/render/access helpers
- `app/web/employee_routes.py` владеет employee React/API surface и classic employee tails
- `app/web/bulk_action_routes.py` владеет bulk React/API surface и classic bulk tails
- `app/web/settings_routes.py` владеет settings React/API surface и classic settings/account tails
- `app/web/scenario_routes.py` владеет scenario/survey React/API workspace, classic editor routes и survey export

# Почему так

- Это снимает главный backend bottleneck: route ownership больше не размазан по одному файлу.
- Это лучше, чем создавать еще больше “переходных” модулей вроде отдельного `scenario_editor_routes.py`, потому что ownership остается вертикальным, а не дробится по случайным слоям.
- Это не равнозначно мгновенному удалению classic fallback surfaces: после выноса ownership нужен parity/remove pass, иначе можно сломать rollback и operator continuity.

# Последствия

Плюсы:

- `app/main.py` перестал быть центром любого backend-изменения.
- Route-level changes теперь можно коммитить и тестировать по вертикальным slice-модулям.
- Следующий cleanup можно делать уже как продуктовый выбор: что сохранить как fallback, а что удалить.

Минусы:

- Classic fallback still exists, просто ownership уже вынесен из монолита.
- Shared helper boundaries между `app/web/*` еще требуют отдельной нормализации.
- Smoke coverage все еще selective, а не полная.

# Что дальше

Следующий шаг не создавать новый slice, а пройтись по remaining classic pages и form actions:

1. подтвердить parity критичных сценариев;
2. удалить ненужные fallback pages;
3. отдельно дочистить shared helper/API drift там, где route ownership уже стабилизирован.
