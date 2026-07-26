# End-to-end tests (Playwright)

These drive a **real running RomM instance** — app, backend and database — unlike
the Vitest specs, which mount components in isolation. They exist to cover
behaviour that only shows up in the assembled app: chiefly **permission gating**,
where the question "is this button visible?" depends on grants resolved by the
backend and projected through `useCan`.

They live in `e2e/` rather than `src/` or `test/` because Vitest's globs
(`src/**/*.{test,spec}.ts`, `test/**/*.{test,spec}.ts`) would otherwise try to
run them in jsdom.

## Running them

1. Have the app up and reachable (default `http://localhost:3000`, override with
   `E2E_BASE_URL`), with a populated library — the specs pick the first ROM they
   find.

2. Seed the two fixture users, from `backend/`:

   ```bash
   uv run python tools/seed_e2e_users.py     # --remove to clean up afterwards
   ```

3. Run, from `frontend/`:

   ```bash
   npm run test:e2e          # headless
   npm run test:e2e:ui       # interactive, for debugging a failure
   ```

## The two fixture users

Every gating spec asserts **both sides**, which is the point:

| User         | Grants                                                         | Expectation                      |
| ------------ | -------------------------------------------------------------- | -------------------------------- |
| `e2e_viewer` | "Viewer (legacy)" group — library read, own collections/assets | write affordances **absent**     |
| `e2e_admin`  | role=admin, so `useCan` short-circuits                         | the same affordances **present** |

Asserting only the viewer side would let a spec pass against a page that failed
to render at all, and would not notice a fix that over-hides and breaks admins.
Where a section is per-user rather than ROM-scoped (e.g. "My screenshots"), the
spec asserts it _stays_ writable for the viewer.

## Notes for whoever edits these

- **Scope to the visible panel** in the Media tab. It keeps every subtab mounted
  (`v-show`, not `v-if`) so the heavy async panels don't re-mount on each switch,
  which means a document-wide locator also matches hidden panels.
- **Prefer auto-waiting assertions** (`expect(locator)`) over bare `count()`.
  `count()` resolves immediately and reads `0` before an async panel mounts,
  which silently turns a real check into a no-op.
- **Keep the worker pool small.** All workers hit one dev server whose on-demand
  Vite transforms are the bottleneck; too much parallelism turns passes into
  timeouts. Tune with `E2E_WORKERS`.
- Not wired into CI — that needs a backend, database and library fixture in the
  runner. Run locally when touching permission gating.
