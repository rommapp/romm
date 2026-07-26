import { defineConfig, devices } from "@playwright/test";

// End-to-end suite. Unlike the Vitest specs (which live beside the code under
// `src/**`), these drive a REAL running RomM instance: the app on
// E2E_BASE_URL, a live backend, and the fixture users seeded by
// `backend/tools/seed_e2e_users.py`. They are deliberately kept out of `src/`
// and `test/` so Vitest's globs never pick them up.
//
//   uv run python tools/seed_e2e_users.py   # once, from backend/
//   npm run test:e2e
export default defineConfig({
  testDir: "./e2e",
  // Compiles the app once before the suite so no single test pays Vite's cold
  // start out of its own timeout.
  globalSetup: "./e2e/global-setup.ts",
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
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  // Start the Vite dev server unless we were pointed at an instance that is
  // already up (E2E_BASE_URL). Locally `reuseExistingServer` attaches to the
  // `npm run dev` you already have running instead of starting a second one.
  //
  // The dev server is used rather than `vite preview` because the /api and /ws
  // proxies are declared under Vite's `server` block, which preview ignores. It
  // proxies to 127.0.0.1:DEV_PORT (default 5000) -- the same default the
  // backend's `main.py` binds -- so neither side needs configuring.
  ...(process.env.E2E_BASE_URL
    ? {}
    : {
        webServer: {
          command: "npm run dev",
          url: "http://127.0.0.1:3000",
          reuseExistingServer: !process.env.CI,
          // Cold start pays for `build:tokens` plus Vite's dep optimisation.
          timeout: 180_000,
          stdout: "pipe" as const,
          stderr: "pipe" as const,
        },
      }),
});
