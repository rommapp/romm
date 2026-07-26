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
Valkey service containers, migrations, `.github/scripts/seed_e2e_library.py` (an
offline scan of `backend/romm_test/library`, no metadata providers), the fixture
users, then the backend, then Playwright. The report and `test-results/` are
uploaded as an artifact when it fails.

**CI serves the built bundle, not the dev server.** Playwright's `webServer`
runs `npm run build && npm run preview` when `CI` is set. `vite preview`
inherits `server.proxy`, so `/api` and `/ws` still reach the backend. This is
both faster (build ~5s, suite ~35s, versus ~3.7min on the dev server) and
steadier — see the next section for what it removes.

Locally it stays on the dev server so a code change is picked up without a
rebuild, and `reuseExistingServer` attaches to the `npm run dev` you already
have. The trade-off is that against a cold dev server the first test or two can
time out while Vite compiles; they recover on the configured retry, so the run
still passes. To get CI's behaviour locally — build once, then a fast, steady
run — use `CI=1 npm run test:e2e` (it needs port 3000 free).

`DEV_PORT` (5000) is both what `main.py` binds and what Vite's `/api` proxy
targets by default, which is why neither side needs configuring.

## Two sources of flakiness, and how they're handled

**1. The Vite dev server reloads underneath you.** It force-reloads the page
when it discovers a new dependency to pre-bundle:

```text
[vite] ✨ new dependencies optimized: vuetify/components/VCombobox
[vite] ✨ optimized dependencies changed. reloading
```

That wipes a half-filled form, so a login silently does nothing and the spec
fails later on an unrelated-looking assertion. CI avoids this entirely by
serving a build. Locally, `login()` retries the fill-and-submit, treating a
reload as the infrastructure event it is.

Symptom to recognise: a couple of tests fail while the rest pass, they pass in
isolation, and the set changes between runs. That's this, not the app.

**2. Assertions racing async store hydration.** This one survives the switch to
a static build, because it's about the app, not the server. `useCan` reads a
store filled from `/permissions/me` _after_ mount, and views render a skeleton
until the auth store has a user. Assert too early and an admin's menu looks
exactly like a permissions bug.

`gotoHydrated()` (used by `gotoFirstRom` / `gotoOwnProfile`) waits for the
permissions response **and** for the app bar to render before returning. Prefer
`expect.poll` over a one-shot `menuLabels()` read when asserting that something
is present, so the menu can still fill in.

## Notes for whoever edits these

- **Scope to the visible panel** in the Media tab. It keeps every subtab mounted
  (`v-show`, not `v-if`) so the heavy async panels don't re-mount on each switch,
  which means a document-wide locator also matches hidden panels.
- **Prefer auto-waiting assertions** (`expect(locator)`) over bare `count()`.
  `count()` resolves immediately and reads `0` before an async panel mounts,
  which silently turns a real check into a no-op.
- **Keep the worker pool small.** All workers share one backend, and locally one
  dev server whose on-demand transforms are the bottleneck; too much parallelism
  turns passes into timeouts. Tune with `E2E_WORKERS`.
- **Watch best-effort `.catch()` calls.** A swallowed failure still waits out its
  full timeout first, eating the budget of the test that follows. Keep those
  timeouts short.
- **The service worker is blocked** (`serviceWorkers: "block"`). The production
  build precaches ~9MB, which every fresh context would re-install, and its
  cache makes runs non-deterministic. Nothing here tests offline support.
