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
