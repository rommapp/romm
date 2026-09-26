# RomM - Repository Guide for Contributors & Agents

RomM is a self-hosted ROM manager and player: scan a game library off disk, enrich it with metadata from 10+ providers, browse it in a web UI, and play in the browser.

---

The frontend talks to the backend over `/api/*` (REST) and `/ws` (Socket.IO). TypeScript types are **generated** from the backend's OpenAPI schema into `frontend/src/__generated__/` - the backend is the single source of truth for API shapes.

## Deep-dive references

- **`docs/BACKEND_ARCHITECTURE.md`** - directory map, ER diagram, every endpoint, auth/scopes, tasks.
- **`docs/FRONTEND_ARCHITECTURE.md`** - routing, stores, services, theming, build tooling.
- **`DEVELOPER_SETUP.md`** - Docker and manual local setup (mock library, `.env`, services).
- **`CONTRIBUTING.md`** - contribution flow, **AI-assistance disclosure**, translations.

---

## Stack-specific guidance

`frontend/CLAUDE.md` (v1 vs v2, frontend commands) and `backend/CLAUDE.md` (backend commands) load when you work in those directories. New frontend work goes in v2 (`frontend/src/v2/`); v1 is frozen.

---

## Skills - load the focused guide for your task

These live in `.claude/skills/` and carry the detailed rules. Invoke the one that matches what you're doing. `pr-ready`, `address-bot-reviews`, and `draft-announcement` are run by the user, not auto-invoked.

---

## Repo-wide rules

**Disclose AI assistance in the PR.** RomM requires it (see `CONTRIBUTING.md`): state that AI was used and to what extent. This is mandatory and non-negotiable for agent-written contributions.
**Branch off `master`; open PRs against `master`.** Fork → feature branch → PR. Don't push to `master`.
**Linting is via [Trunk](https://trunk.io)** (`trunk fmt && trunk check`), which wraps ruff, black, isort, ESLint, Prettier, and more, and runs in CI on every PR. **Never commit with `--no-verify`.**
**The backend owns the API contract.** Changed a response schema or route? Regenerate frontend types (`npm run generate`) and re-typecheck.
**Tests travel with code.** New logic gets a test; new endpoints get endpoint tests; new v2 primitives get a Storybook story (+ `play()` if interactive).
**Verify before handoff.** Don't say "done" on UI work without testing it in the browser in both themes and all input modalities. See `review-polish`.
**English first.** Outside of language files, all code, comments, identifiers, `.md` files, and commit/PR messages are in English.
**No em-dashes.** Never use em-dashes (U+2014) when writing comments or text. Use commas, parentheses, or separate sentences instead. An em-dash string literal is code (an empty-value glyph) and stays allowed.
**Prefer a check to a model review.** A mechanical rule (an import, a character, a CSS pattern, an SFC shape) belongs in ESLint, `tsconfig`, or Trunk. When a review finding repeats, propose a check as a named follow-up; see `review-polish`.
**Keep comments short.** Comments should be concise, and focus on the "why" rather than the "what" (the code itself is the "what"). A comment is one or two lines; a docstring is one sentence plus `Args:`/`Returns:` when the signature needs it. Three or more lines of prose means you are explaining, not commenting. See `review-polish` for what to cut.
**Don't restate the code.** The code is self-documenting, so skip comments that narrate what a reader can already see (which button sits where, that something is disabled when empty, obvious ordering). Comment only non-obvious "why" that the code can't convey on its own.
**One home per value.** Before declaring a constant, type, limit, regex, or store getter, search for an existing one and import it. Validation limits live on the model and are imported by endpoints; a type lives in the component that owns it and is exported. Don't add a near-duplicate that differs only by sorting, and don't invent an identity scheme where a foreign key already exists.
**Never commit secrets.** Never commit secrets (API keys, passwords, tokens, etc.) to the repo. Use environment variables or secret management tools instead.
**Don't explain a change.** Avoid comments that explain why a change was made to the code, or that record what the code used to do. Focus instead on the current behaviour of the code and how it works. Reasons for a change go in the commit message and the PR body.
**Python tools live in `backend/tools/`.** Standalone dev/test utilities and scripts (not part of the app runtime) go in `backend/tools/`, not scattered across `backend/`.
**Link PRs to issues.** In the PR description, use `Fixes #XXXX` for issue/bug fixes and `Closes #XXXX` for feature implementations.
**Use the PR template.** Base every PR description on `.github/PULL_REQUEST_TEMPLATE.md`.
**Show UI changes in the PR.** A PR that touches anything visible ships with at least one screenshot under the template's `Screenshots` heading, captured from the running app during the `review-polish` browser pass. Enough shots to convey what changed, not a catalogue of every state. Save the files outside the repo and never commit them, and upload them with `gh pr create --attach` (or `gh pr edit --attach` on an existing PR) rather than handing the paths to the user.
**Diagram architectural changes in the PR.** When a change moves a boundary (a new service, task, or provider in a path, a model relationship, a different call path across layers, an auth or socket flow), the PR description carries a `mermaid` block showing it. GitHub renders them. Draw what changed, not the whole system. See `review-polish`.

---

## Quick command reference

**Setup:** see `DEVELOPER_SETUP.md`. Docker path is `cp env.template .env` → `docker compose build` → `docker compose up -d` (app at `http://localhost:3000`).

**Lint (both stacks):** `trunk fmt && trunk check`.
