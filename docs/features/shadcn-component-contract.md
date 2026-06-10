---
title: Shadcn Component Contract
date: 2026-06-01
status: active
doc_type: feature
area: frontend
source_of_truth: true
---

# Shadcn Component Contract

## Runtime

- Frontend stack: Vite React, Tailwind v4, shadcn `base-nova`, Base UI primitives.
- `frontend/components.json` must stay Vite-compatible: `rsc: false`, `tailwind.css: src/index.css`, aliases under `@/`.
- Do not copy Next/RSC examples literally into this project. Adapt examples to the local Vite runtime.
- Before adding or rewriting a shared component, run `npx shadcn@latest info --json` and `npx shadcn@latest docs <component>`.

## Mandatory Shadcn Workflow

- Treat the local shadcn skill rules as an execution gate for admin UI work, not as optional guidance.
- Before changing a component or page composition, run `npx shadcn@latest info --json` from `frontend` and verify `base`, aliases, Tailwind version, CSS file, and installed components.
- Before using or changing a shadcn component, run `npx shadcn@latest docs <component>` and inspect the local component source in `frontend/src/components/ui`.
- If a needed component is missing, search and preview first: `npx shadcn@latest search ...`, then `npx shadcn@latest add <component> --dry-run`, then `--diff` when updating an existing file. Do not add registry code blindly.
- If a page needs a new composition pattern, add it to `/app/design-system#patterns` first, then apply it to the live page.
- After adding registry files or community blocks, read the generated files before continuing. Fix imports, `SelectGroup`/item grouping, Base UI `render` usage, icon sizing, semantic tokens, and Vite incompatibilities immediately.
- Do not use raw internet snippets, Next/RSC examples, or registry blocks as-is. They must be adapted to this Vite + Base UI + Tailwind v4 project.
- If the shadcn docs and current local implementation disagree, prefer the local implementation for runtime behavior and update this contract or the component deliberately.

## Primitive Policy

- New shared UI must use shadcn Base components first.
- Do not introduce new Radix wrappers for admin UI. Existing Radix-based wrappers are migration debt and must be replaced with Base UI equivalents before they become new dependencies.
- Use Base UI `render` composition, not Radix `asChild`.
- Shared trigger components used with Base UI `render` must forward refs. `Button` is ref-forwarding for this reason; do not convert it back to a plain function component.
- Do not create page-local imitations of controls when a shared primitive exists.
- Use `Button`, `Input`, `Textarea`, `Select`, `Checkbox`, `Switch`, `Field`, `Card`, `Table`, `Badge`, `Alert`, `Empty`, `Popover`, `Dialog`, `AlertDialog`, `DropdownMenu`, `Tooltip` from `frontend/src/components/ui`.
- Emoji insertion uses `EmojiPickerPopover` from `frontend/src/components/ui/emoji-picker-popover.tsx`: trigger is the shared `Button`, overlay is the shared `Popover`, `emoji-picker-react` is lazy-loaded, and the public API is only `onEmojiSelect(emoji: string)`.
- Destructive confirmations use `ConfirmAction` from `frontend/src/components/ui/confirm-action.tsx`; do not use `window.confirm` in React admin pages. Keep destructive color on the confirmation action inside the dialog, not on every delete icon in dense page grids.

## Token Policy

- Source of truth for tokens: `frontend/src/index.css`.
- Tokens use Tailwind v4 `@theme inline` plus CSS variables in `:root` and `.dark`.
- Page width/radius baseline: regular admin pages use `--admin-page-max-width: 1820px`, `--admin-page-radius`, `.admin-page-shell`, `.admin-page-stack`, and `.admin-page-surface`. Do not add new page-local `max-w-[1680px]`, `max-w-[1760px]`, `max-w-[1960px]`, or ad-hoc main container radii.
- Color values use OKLCH. Do not add new hex UI tokens unless the palette is explicitly revised.
- Do not use default Tailwind UI colors such as `gray-*`, `slate-*`, `zinc-*`, `green-*`, `red-*`, `blue-*`, `amber-*` in new admin surfaces.
- Use semantic tokens only: `bg-background`, `text-foreground`, `bg-card`, `text-muted-foreground`, `border-border`, `border-input`, `ring-ring`, `bg-primary`, `text-primary-foreground`.
- Custom status tokens are allowed through `success`, `warning`, `info` and their `*-foreground` pairs.

## Forms And Controls

- Form groups use `FieldGroup`, `Field`, `FieldLabel`, `FieldDescription`, not page-local label/div stacks.
- Selects use shadcn/Base `Select`, not native select, unless browser-native behavior is explicitly required.
- Date and time controls use shared date/time primitives. Do not use native `input[type=date]`, `input[type=time]`, or `input[type=datetime-local]` for operator UI.
- Checkboxes use shared `Checkbox`, not raw `input[type=checkbox]`.
- Validation uses `aria-invalid` on the control and tokenized destructive styles.
- Browser autofill must stay tokenized. Keep `:-webkit-autofill` overrides in `frontend/src/index.css` so saved emails, names, and addresses do not repaint controls to white in light or dark theme.

## Feedback

- Toasts use shadcn Base `sonner`.
- In this Vite project, Sonner must read theme from `frontend/src/lib/theme.ts` or explicit props. Do not use `next-themes`.
- Sonner styles must use `--popover`, `--popover-foreground`, `--border`, `--radius`, and semantic status tokens.

## Required Update Loop

- If a shared primitive changes, update `/app/design-system` in the same change.
- If a page introduces a new visual pattern, document it in `/app/design-system` or this file.
- `/app/settings` and `/app/bulk-actions` must follow the `Settings form` and `Bulk action console` examples in `/app/design-system#patterns`.
- Run `npm run build` after shared UI changes.
- Browser smoke at minimum: `/app/design-system` plus the page that consumes the changed primitive.
- Update `docs/handoffs/frontend-structure-reset-handoff.md` with touched screens, shared UI API changes, checks, and known issues.

## Current Migration Debt

- Older Radix wrappers may still exist elsewhere, but `frontend/src/components/ui/scroll-area.tsx` is now the Base UI wrapper and should be used for custom scroll regions.
- Some older pages still contain raw Tailwind color classes such as red/amber statuses. Replace them with semantic tokens during the next page pass.
- `frontend/src/components/ui/sonner.tsx` exists but is not Vite-correct because it imports `next-themes`. Replace it before using Sonner in production admin flows.
