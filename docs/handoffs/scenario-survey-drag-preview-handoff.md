---
title: Scenario And Survey Drag Preview Handoff
date: 2026-06-16
status: active
doc_type: handoff
area: frontend
related:
  - "[[project_state]]"
  - "[[backlog]]"
source_of_truth: false
---

# Scenario And Survey Drag Preview Handoff

## Changed

- Scenario and survey list dragging now uses a compact custom drag preview instead of the browser-rendered full card silhouette.
- Root step/question dragging in the central workspace uses the same compact preview.
- Existing reorder mechanics and API calls were not changed.
- Existing drop-target highlight and captured-item dimming remain in place.

## Screens

- `/app/flows/workspace-v2`
- `/app/surveys/workspace`

## Shared UI API

- No shared component API changed.

## Checks

- `npm run build`
- `.\.venv\Scripts\python.exe -m compileall app`
- `.\.venv\Scripts\python.exe -m unittest tests.test_scenario_engine_smoke tests.test_messaging_identity tests.test_employee_api_smoke -v`
- Browser smoke on scenarios and surveys: page identity, non-empty render, console health, screenshot, and same-item drag gesture.

## Deploy Boundary

- Not deployed directly to stage from this branch.
- `docs/stage-change-log.md` was intentionally not updated because final stage rollout is handled separately after parallel feature branches are merged.
