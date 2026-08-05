---
title: Operational dashboard as default admin entry
date: 2026-06-08
status: accepted
doc_type: adr
area: frontend
related:
  - "[[architecture]]"
  - "[[api]]"
  - "[[web-surface]]"
source_of_truth: true
---

# Operational dashboard as default admin entry

## Решение

Default entry для авторизованной админки теперь `/app/dashboard`. Root `/`, успешный login и бренд/иконка бота в sidebar ведут на dashboard. Отдельный пункт “Главная” в primary nav не добавляется, потому что бренд уже является компактным входом на главную и второй пункт создавал бы дублирование.

## Почему

Список сотрудников/кандидатов стал слишком узкой стартовой точкой: оператору сначала нужна оперативная картина, а не один модуль. Dashboard v1 показывает ближайшие scheduled launches/actions, свежие Telegram-привязки кандидатов, inbound files, attention items и переходы в существующие модули.

## Границы

- Dashboard read-only и не выполняет destructive/write actions.
- “Регистрация кандидата в боте” в v1 трактуется как active Telegram-привязка кандидата из `employee_messenger_accounts`.
- Полноценный audit trail регистраций не вводится; если он понадобится, нужно проектировать отдельную event/audit модель.
