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

2. Seed the two fixture users, from the repo root:

   ```bash
   uv run python .github/scripts/seed_e2e_users.py   # --remove to clean up afterwards
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

## In CI

`.github/workflows/e2e.yml` runs the whole thing on `ubuntu-latest`: MariaDB +
Valkey service containers, migrations, `.github/scripts/seed_e2e_library.py` (an offline
scan of `backend/romm_test/library`, no metadata providers), the fixture users,
then the backend, then Playwright — whose `webServer` starts the Vite dev server.
The report and `test-results/` are uploaded as an artifact when it fails.

`DEV_PORT` (5000) is both what `main.py` binds and what Vite's `/api` proxy
targets by default, which is why neither side needs configuring.

## The Vite reload gotcha

Most flakiness here traces to one thing. The dev server force-reloads the page
when it discovers a new dependency to pre-bundle:

```text
[vite] ✨ new dependencies optimized: vuetify/components/VCombobox
[vite] ✨ optimized dependencies changed. reloading
```

That wipes a half-filled form, so a login silently does nothing and the spec
fails later on an unrelated-looking assertion. Two defences, both load-bearing:

- `global-setup.ts` does a **passive** pass (navigate only, no interaction)
  before anything else, so the reload happens while nothing depends on the page.
  It then walks the routes under test to compile their lazy chunks.
- `login()` retries the fill-and-submit, treating a reload as the infrastructure
  event it is.

Symptom to recognise: a couple of tests fail while the rest pass, they pass in
isolation, and the set changes between runs. That's this, not the app.

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
- **Don't duplicate the helpers.** `global-setup.ts` drives the same `login()` /
  `gotoFirstRom()` as the specs on purpose; a private copy of those selectors
  drifted from the real ones within a day of being written.
- **Watch best-effort `.catch()` calls.** A swallowed failure still waits out the
  full timeout first. Warm-up steps set a short one deliberately — inheriting the
  120s default turned a 30-second setup into an eight-minute one.
- `E2E_SKIP_WARMUP=1` skips the warm-up when debugging a single spec against an
  already-warm server.
