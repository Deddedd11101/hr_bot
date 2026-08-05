---
title: Локальный запуск HR Bot
date: 2026-05-13
status: active
doc_type: runbook
area: deploy
task_tokens:
  - HRB-DOC-04
related:
  - "[[README]]"
  - "[[configuration]]"
  - "[[stage-deploy]]"
source_of_truth: true
review_after: 2026-06-01
---

# Локальный запуск

Этот runbook фиксирует текущий рабочий способ запуска проекта локально на Windows.

## Рабочая директория

Все команды выполнять из корня проекта:

```powershell
cd D:\HRBot\hr_bot
```

## Админка

Основная команда:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

После запуска открыть:

```text
http://127.0.0.1:8000
```

## Telegram bot worker

Если нужно отдельно поднять bot worker:

```powershell
.\.venv\Scripts\python.exe -m app.bot_runner
```

## Frontend assets

Для обычной проверки админки Vite dev server поднимать не нужно: React assets собираются в `app/static/workspace_v2`.

Если менялся код в `frontend/src`, пересобрать assets:

```powershell
cd D:\HRBot\hr_bot\frontend
npm run build
```

После сборки вернуться в корень проекта перед запуском админки.

## Проверка документации

Если менялись docs, API routes, config vars или SQLAlchemy models:

```powershell
cd D:\HRBot\hr_bot
.\.venv\Scripts\python.exe tools\check_docs_contracts.py
```

Эта проверка не заменяет backend/frontend тесты. Она ловит рассинхрон между docs и базовыми code contracts.

## Про `--reload`

`--reload` не является основной командой для этого проекта.

Использовать его можно только как optional dev-mode, если он стабильно работает в текущем окружении:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Если есть сомнения, запускать без `--reload`.
