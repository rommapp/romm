import { defineConfig, devices } from "@playwright/test";

// End-to-end suite.
//   uv run python .github/scripts/seed_e2e_users.py   # once, from the repo root
//   npm run test:e2e
export default defineConfig({
  testDir: "./e2e",
  // Permission gating is global state on the server (the fixture users' grants),
  // so the specs read it rather than mutate it and are safe to parallelise.
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 1,
  // Every worker logs in and hammers ONE dev server, whose on-demand Vite
  // transforms are the bottleneck. Too many workers turns real passes into
  // timeouts, so keep the pool small.
  workers: Number(process.env.E2E_WORKERS ?? 2),
  reporter: process.env.CI ? "github" : "list",
  timeout: 45_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
    // The production build ships a PWA service worker that precaches ~9MB on
    // first load. Every test gets a fresh context, so that install would run
    // over and over, competing with the app for the first navigation, and its
    // cache makes runs non-deterministic. Nothing here tests offline support.
    serviceWorkers: "block",
  },
  projects: [
    // Logs each fixture user in once and saves the session; every spec then
    // starts authenticated via `test.use({ storageState })` instead of driving
    // the login form again. login.spec.ts is the one place the form itself is
    // exercised, and it opts out by using a fresh page.
    {
      name: "setup",
      testMatch: /.*\.setup\.ts/,
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "chromium",
      testIgnore: /.*\.setup\.ts/,
      use: { ...devices["Desktop Chrome"] },
      dependencies: ["setup"],
    },
  ],
  // Serve the app unless we were pointed at an instance that is already up
  // (E2E_BASE_URL).
  //
  // CI builds and serves the STATIC bundle. The dev server compiles on demand,
  // and force-reloads the page whenever it discovers a new dependency to
  // pre-bundle ("optimized dependencies changed. reloading") -- which wipes
  // whatever a test was mid-way through. Serving a build removes that entire
  // class of failure and is much faster: the build is ~5s and the suite drops
  // from ~3.7min to ~35s. `vite preview` inherits `server.proxy`, so /api and
  // /ws still reach the backend on DEV_PORT (5000) -- the same default
  // `main.py` binds, so neither side needs configuring.
  //
  // Locally it stays on the dev server: `reuseExistingServer` attaches to the
  // `npm run dev` you already have, so a code change is picked up without a
  // rebuild. `login()` retries to absorb the reload described above.
  ...(process.env.E2E_BASE_URL
    ? {}
    : {
        webServer: {
          command: process.env.CI
            ? "npm run build && npm run preview -- --port 3000 --strictPort --host 127.0.0.1"
            : "npm run dev",
          url: "http://127.0.0.1:3000",
          reuseExistingServer: !process.env.CI,
          timeout: 180_000,
          stdout: "pipe" as const,
          stderr: "pipe" as const,
        },
      }),
});
