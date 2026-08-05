---
title: Stage-first delivery pipeline
date: 2026-08-05
status: accepted
doc_type: adr
area: deploy
related:
  - "../subagent-delivery.md"
  - "../stage-deploy.md"
  - "../stage-change-log.md"
source_of_truth: true
---

# Stage-first delivery pipeline

## Контекст

Проект долго развивался через параллельные Codex/subagent ветки, локальные worktree, прямые stage-интеграции и иногда ручные операции с SQLite. Это позволило быстро двигаться, но привело к накоплению исторических веток, dirty worktree и размытию ответа на вопрос "что уже реально на стенде".

Дополнительное ограничение проекта: полноценная локальная проверка Telegram-поведения затруднена, потому что stage использует серверный WireGuard route к Telegram. Поэтому тестовый стенд остается главным runtime validation environment.

## Решение

Принимаем stage-first delivery model:

- `origin/stage` — единственная supported integration branch для test/stage deploy.
- `main` — default branch для baseline, workflows и process changes; она не является обычным stage deploy ref.
- Субагенты работают как разработчики: отдельная feature branch/worktree, commit, push, PR-ready handoff или draft PR.
- Нет прямого deploy feature-веток на общий stage.
- Интегратор review'ит diff/scope/checks, собирает approved changes в `stage`, запускает GitHub Actions `Deploy Stage` с `ref=stage`, проверяет smoke и пишет `docs/stage-change-log.md`.
- Старые ветки нельзя мержить по имени. Сначала выполняется readiness/classification: live, superseded, needs rebuild. Если ветка старая, но идея живая, делается fresh rebuild от актуального `origin/stage`.
- После successful deploy feature worktree/branches должны быть удалены или явно сохранены как future idea. Dirty worktree не должен переживать один integration cycle без rescue snapshot.

## Workflow

1. Создать clean worktree от `origin/stage`.
2. Сделать маленький scope change.
3. Обновить docs вместе с кодом.
4. Прогнать релевантные проверки.
5. Запушить feature branch.
6. Передать PR-ready handoff или открыть draft PR.
7. Провести review.
8. Интегратор собирает `stage`.
9. GitHub Actions deploy делает preflight, SQLite backup, service restart, HTTP/Telegram smoke.
10. Интегратор фиксирует deploy в `docs/stage-change-log.md`.
11. Feature branch/worktree cleanup.

## Consequences

Плюсы:

- меньше незакоммиченного локального состояния;
- stage всегда соответствует одному понятному git ref;
- легче понять, какие изменения реально выведены;
- меньше риска перетереть backend frontend-веткой или наоборот;
- cleanup становится частью delivery, а не отдельным пожаром.

Минусы:

- больше дисциплины на маленьких branches/PR-ready handoffs;
- быстрые микроправки тоже проходят review/integration gate;
- если SMTP/VPN/stage infra не готова, feature может быть подготовлена, но не deployed.

## Explicit non-goals

- Не вводим автоматический deploy `main`.
- Не считаем stage SQLite source of truth для application code.
- Не деплоим старые feature branches без rebuild.
- Не используем `D:\HRBot\hr_bot` как обычный рабочий каталог для новых задач, пока он остается dirty historical container.
