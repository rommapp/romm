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
});
