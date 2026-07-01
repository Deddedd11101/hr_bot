---
title: Stage admin HTTPS baseline
date: 2026-07-01
status: accepted
doc_type: decision
area: infra
related:
  - "../stage-deploy.md"
  - "../configuration.md"
  - "../web-surface.md"
---

# Stage admin HTTPS baseline

## Решение

Для тестового admin-доступа выбран простой baseline: домен, HTTPS reverse proxy и закрытый публичный доступ к приложению на `:8000`.

Целевой контур:

- DNS `A` для admin-домена указывает на `92.51.38.32`;
- reverse proxy слушает `80/443` и проксирует в `127.0.0.1:8000`;
- FastAPI остается доступен локально для systemd и deploy smoke checks;
- внешний `:8000` закрывается firewall;
- после включения HTTPS на stage выставляются `ADMIN_SESSION_SECRET=<long random secret>` и `ADMIN_SESSION_COOKIE_SECURE=true`.

## Почему не VPN-only сейчас

VPN-only доступ усложняет тестирование, поддержку и передачу стенда пользователям. Для текущего stage разумнее сначала убрать plain HTTP и прямой app-port из публичного доступа, а затем при необходимости добавить IP allowlist или Basic Auth на proxy.

## Последствия

- GitHub Actions deploy path не должен меняться: workflow может продолжать проверять `http://127.0.0.1:8000/...` на сервере.
- После включения `ADMIN_SESSION_COOKIE_SECURE=true` вход по plain HTTP перестанет быть валидным, поэтому эту переменную нельзя включать до рабочего HTTPS.
- Смена `ADMIN_SESSION_SECRET` принудительно инвалидирует старые signed-cookie сессии.
