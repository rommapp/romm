# RomM - Repository Guide for Contributors & Agents

RomM is a self-hosted ROM manager and player: scan a game library off disk, enrich it with metadata from 10+ providers, browse it in a web UI, and play in the browser.

---

## The stack at a glance

|           | Backend                                     | Frontend                                  |
| --------- | ------------------------------------------- | ----------------------------------------- |
| Path      | `backend/`                                  | `frontend/`                               |
| Language  | Python 3.13+                                | TypeScript 5.7 (Vue 3)                    |
| Framework | FastAPI, SQLAlchemy 2.0, Alembic            | Vue 3 + Vite, Vuetify, Pinia, Vue Router  |
| Infra     | Redis + RQ (jobs/cache/sessions), Socket.IO | vue-i18n, Socket.IO client                |
| DB        | MariaDB (default), MySQL, PostgreSQL        | -                                         |
| Tooling   | `uv`, pytest, Trunk (ruff/black/isort/mypy) | `npm`, vue-tsc, ESLint, Vitest, Storybook |

The frontend talks to the backend over `/api/*` (REST) and `/ws` (Socket.IO). TypeScript types are **generated** from the backend's OpenAPI schema into `frontend/src/__generated__/` - the backend is the single source of truth for API shapes.

### Deep-dive references

- **`docs/BACKEND_ARCHITECTURE.md`** - directory map, ER diagram, every endpoint, auth/scopes, tasks.
- **`docs/FRONTEND_ARCHITECTURE.md`** - routing, stores, services, theming, build tooling.
- **`DEVELOPER_SETUP.md`** - Docker and manual local setup (mock library, `.env`, services).
- **`CONTRIBUTING.md`** - contribution flow, **AI-assistance disclosure**, translations.

---

## The frontend has two UIs - know which you're in

- **v1 is frozen.** Everything under `frontend/src/views/`, `src/components/`, `src/console/`, `src/layouts/` is legacy and will be deleted wholesale in a final wave. **Do not refactor v1.** Only touch it for a critical bug, and when a v2 fork exists, mark the v1 export `@deprecated`.
- **v2 is the active rewrite** under `frontend/src/v2/`, gated by `user.ui_settings.uiVersion`. It has its own design system (tokens), primitive library (`R*` components in `src/v2/lib/`), universal input (mouse/touch/keyboard/gamepad), and responsive system. New frontend work goes in v2.

v2 has a detailed constitution, split across focused skills (below). **Read the relevant skill before editing v2 code.**

---

## Skills - load the focused guide for your task

These live in `.claude/skills/` and carry the detailed rules. Invoke the one that matches what you're doing:

| Skill                    | When                                                                                                                                 |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------ |
| `frontend-v2-components` | Building/editing any v2 component - tiers (lib/shared/feature), file & SFC conventions, barrels, anti-patterns.                      |
| `frontend-v2-theming`    | Colors, tokens, light/dark themes, visual language - and the **zero-hex-literal** policy.                                            |
| `frontend-v2-input`      | Interactive components, focus/spatial navigation, gamepad/keyboard, breakpoints & responsive layout.                                 |
| `frontend-v2-patterns`   | Feature behavior - errors/snackbars, loading, sockets, state persistence, pagination, forms, permissions, destructive confirmations. |
| `frontend-i18n`          | Any user-visible string or change under `frontend/src/locales/**`.                                                                   |
| `backend-development`    | Endpoints, handlers, models, schemas, metadata adapters, tasks, migrations under `backend/`.                                         |
| `pre-pr-verification`    | Before committing / opening a PR / declaring done - the checks that keep CI green.                                                   |

---

## Repo-wide rules

**Disclose AI assistance in the PR.** RomM requires it (see `CONTRIBUTING.md`): state that AI was used and to what extent. This is mandatory and non-negotiable for agent-written contributions.
**Branch off `master`; open PRs against `master`.** Fork → feature branch → PR. Don't push to `master`.
**Linting is via [Trunk](https://trunk.io)** (`trunk fmt && trunk check`) — it wraps ruff, black, isort, mypy, ESLint, Prettier, and more, and runs in CI on every PR. **Never commit with `--no-verify`.**
**The backend owns the API contract.** Changed a response schema or route? Regenerate frontend types (`npm run generate`) and re-typecheck.
**Tests travel with code.** New logic gets a test; new endpoints get endpoint tests; new v2 primitives get a Storybook story (+ `play()` if interactive).
**Verify before handoff.** Don't say "done" on UI work without testing it in the browser in both themes and all input modalities. See `pre-pr-verification`.
**English first.** Outside of language files, all code, comments, identifiers, `.md` files, and commit/PR messages are in English.
**No em-dashes.** Never use em-dashes (—) when writing comments or text. Use commas, parentheses, or separate sentences instead.
**Keep comments short.** Comments should be concise, and focus on the "why" rather than the "what" (the code itself is the "what"). Avoid long paragraphs; break them into multiple lines or sentences.
**Never commit secrets.** Never commit secrets (API keys, passwords, tokens, etc.) to the repo. Use environment variables or secret management tools instead.
**Don't explain a change.** Avoid comments that explain why a change was made to the code. Focus instead on the current behaviour of the code and how it works.

---

## Quick command reference

**Setup:** see `DEVELOPER_SETUP.md`. Docker path is `cp env.template .env` → `docker compose build` → `docker compose up -d` (app at `http://localhost:3000`).

**Backend** (`cd backend`):

```bash
uv sync --all-extras --dev          # install
uv run main.py              # run (migrations auto-apply)
uv run pytest [path/file]           # test (subset) - or -vv for all
uv run alembic revision --autogenerate -m "msg"   # new migration (then HAND-REVIEW)
uv run alembic upgrade head         # apply migrations
```

Standalone Python tools/scripts (dev/test utilities, not part of the app) live in `backend/tools/`.

**Frontend** (`cd frontend`):

```bash
npm install                         # install (Node 24)
npm run dev                         # dev server :3000
npm run typecheck                   # vue-tsc
npm run test                        # vitest (+ Storybook play() tests)
npm run build                       # production build
npm run generate                    # regenerate types from backend OpenAPI (backend must be running)
npm run build:tokens                # regenerate v2 tokens.css (auto on predev/prebuild)
npm run storybook                   # component library on :6006
python3 src/locales/check_i18n_locales.py   # i18n parity check
```

**Lint (both stacks):** `trunk fmt && trunk check`.
