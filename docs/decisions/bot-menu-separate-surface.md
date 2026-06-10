---
title: Bot menu separate surface
date: 2026-06-09
status: accepted
doc_type: decision
area: frontend
task_tokens:
  - HRB-P1-07
related:
  - "[[project_state]]"
  - "[[architecture]]"
  - "[[web-surface]]"
  - "[[handoffs/frontend-structure-reset-handoff]]"
source_of_truth: true
---

# Решение

Редактор menu sets и audience-targeting больше не живет внутри `/app/settings`.

Для него выделяется отдельная React surface:

- `/bot-menu` -> redirect
- `/app/bot-menu` -> React bootstrap page

`/app/settings` после этого отвечает только за:

- HR/system settings
- admin accounts
- shortcut на управление меню бота

# Почему

- menu sets перестали быть простым набором кнопок и получили отдельную логику audience targeting;
- смешивание system settings, account management и bot-menu rules на одном экране снова превращало `/app/settings` в свалку несвязанных конфигов;
- mini app gating и candidate/staff-only actions дальше будут опираться на тот же targeting contract, поэтому bot menu уже является отдельным модулем, а не второстепенной частью настроек.

# Последствия

- product boundary становится чище: system settings и bot UX rules разнесены по разным экранам;
- sidebar получает отдельный пункт `Меню бота`;
- следующий technical cleanup теперь не “еще одна страница”, а вынос shared helpers/types между `settings` и `bot-menu`, чтобы не поддерживать два почти одинаковых блока логики.
