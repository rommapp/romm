# End-to-end tests (Playwright)

These drive a **real running RomM instance**, unlike the Vitest specs, which mount components in isolation. They exist to cover behaviour that only shows up in the assembled app. They live in `e2e/` rather than `src/` or `test/` because Vitest's globs (`src/**/*.{test,spec}.ts`, `test/**/*.{test,spec}.ts`) would otherwise try to run them in jsdom.

## Running tests

1. Have the app up and reachable (default `http://localhost:3000`, override with `E2E_BASE_URL`), with a populated library — the specs pick the first ROM they find.

2. Seed the two fixture users, from the repo root:

   ```bash
   uv run python .github/scripts/seed_e2e_users.py   # --remove to clean up afterwards
   ```

3. Run, from `frontend/`:

   ```bash
   npm run test:e2e          # headless
   npm run test:e2e:ui       # interactive, for debugging a failure
   ```

## Authentication

`auth.setup.ts` runs first as its own project, logs each fixture user in once and saves the session to `playwright/.auth/` (gitignored). Specs pick an identity with `test.use({ storageState: STORAGE_STATE.viewer })` and start signed in, so the form is driven twice per run rather than once per test.

`login.spec.ts` is the only spec that drives the form, using the default unauthenticated page. If auth breaks, diagnose there.
