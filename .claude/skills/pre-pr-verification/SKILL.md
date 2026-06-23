---
name: pre-pr-verification
description: The before-handoff / before-PR verification gate for RomM, covering both stacks. Use right before committing, opening a PR, or telling the user a change is done — to run the right static checks, tests, and (for UI) manual browser/theme/input/Storybook checks so CI stays green. Covers frontend (typecheck/lint/test/build/i18n/tokens), backend (pytest/alembic/trunk), and the OpenAPI regen step. Trigger when wrapping up any change.
---

# RomM — Verification Before Handoff

Run the checks that match what you touched. **Static checks don't prove a feature works** — when UI changed, also test it in the browser. Mirror the CI gates so review isn't the first place a failure shows up. **Never `--no-verify`.**

---

## Frontend (`frontend/`)

Run from `frontend/`:

1. `npm run typecheck` — zero errors (`vue-tsc --noEmit`).
2. `npm run lint` _(if present)_ / ESLint clean. Trunk also runs ESLint + Prettier in CI.
3. `npm run test` — zero failures (Vitest + happy-dom; runs unit tests **and** every `/lib` story's `play()` via `composeStories`).
4. `npm run build` — zero failures (CI sanity check).

**If you touched the backend API:** start the backend, run `npm run generate`, then re-`typecheck`.

**If you touched tokens** (`src/v2/tokens/index.ts`): `npm run build:tokens` (also auto-runs on `predev`/`prebuild`) and confirm `tokens.css` regenerated.

**If you touched locales** (`src/locales/**`): `python3 frontend/src/locales/check_i18n_locales.py` must pass with zero missing/extra keys. See the `frontend-i18n` skill.

### UI manual pass (when changes are visible) — v2

With `uiVersion = "v2"`:

- **Golden path + edge cases:** empty, error, loading, no-permission, extreme data; plus nearby regressions.
- **Both themes:** `v2-dark` and `v2-light`.
- **All four input modalities:** mouse, touch, keyboard, gamepad — focus ring only on `key`/`pad`.
- **Responsive sweep:** 320px → 4K across the `useBreakpoint` tiers; overlays full-bleed on `xs`.
- **Accessibility:** contrast, keyboard reachability with no traps, aria-labels on icon-only controls.
- **Performance:** lists/grids of 1000+ items stay smooth; every `v-for` has a stable `:key`.

### Storybook (for `/lib`)

- New primitive → mandatory story with controls + at least one variant per theme; interactive ones get a `play()`.
- Modified primitive → existing story still renders and interactions still pass.
- Don't duplicate coverage between Vitest (pure logic) and Storybook `play()` (components).

---

## Backend (`backend/`)

Run from `backend/`:

1. `uv run pytest [path/file]` — zero failures (run the affected subset, or all with `-vv`).
2. `trunk fmt && trunk check` — ruff/black/isort/mypy/bandit clean (CI enforces Trunk).
3. **If you added a migration:** `uv run alembic upgrade head` then `uv run alembic downgrade -1` to prove both directions; it must work on MariaDB **and** PostgreSQL (CI runs both).
4. **If a response schema or route signature changed:** regenerate frontend types (`npm run generate`) and typecheck the frontend.

---

## CI gates this mirrors

`typecheck.yml` (vue-tsc + lockfile lint), `frontend.yml` (vitest + build), `i18n.yml` (locale check), `pytest.yml` (pytest on MariaDB + PostgreSQL), `migrations.yml` (alembic on both DBs), `trunk-check.yml` (Trunk across the repo). Green locally → green in CI.

## Don't

- Open a PR without manually testing the UI when UI was touched.
- `--no-verify` on commits.
- Leave a locale key English-only, a token un-generated, or a migration one-directional.
