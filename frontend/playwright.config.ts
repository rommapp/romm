import { defineConfig, devices } from "@playwright/test";
import { url as inspectorUrl } from "node:inspector";
import { readE2EEnv, webServerEnv } from "./e2e/e2e-environment";
import type { E2EOptions } from "./e2e/fixtures/test";

// End-to-end suite: `npm run test:e2e`. Accounts and the backend under test
// come from e2e/.env (see e2e/.env.example); CI sets them in the workflow.
const env = readE2EEnv();

const isCI = env.CI;
// A test paused on a breakpoint must not be killed by the timeouts below.
const debugging = !!process.env.PWDEBUG || inspectorUrl() !== undefined;
// Off the default dev port, so the suite never collides with a `npm run dev`.
const PORT = 3100;
const ORIGIN = `http://127.0.0.1:${PORT}`;

export default defineConfig<E2EOptions>({
  testDir: "./e2e",
  // Permission gating is global state on the server (the fixture users' grants),
  // so the specs read it rather than mutate it and are safe to parallelise.
  fullyParallel: true,
  forbidOnly: isCI,
  // Retries hide flakes; CI keeps one but still fails a test that needed it.
  retries: isCI ? 1 : 0,
  failOnFlakyTests: isCI,
  maxFailures: isCI ? 5 : 0,
  // Every worker hammers ONE dev server, whose on-demand transforms are the
  // bottleneck, so keep the pool small locally. CI serves a static build.
  workers: env.E2E_WORKERS ?? (isCI ? 4 : 2),
  // The HTML report holds each failure's trace: `npm run test:e2e:report`.
  reporter: [[isCI ? "github" : "list"], ["html", { open: "never" }]],
  // Anything slower is a bug, not a reason to wait. A test that genuinely
  // needs longer uses `test.setTimeout`. 0 means no timeout.
  timeout: debugging ? 0 : 10_000,
  expect: { timeout: debugging ? 0 : 3_000 },
  use: {
    baseURL: ORIGIN,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    actionTimeout: debugging ? 0 : 5_000,
    navigationTimeout: debugging ? 0 : 5_000,
    // The PWA service worker precaches ~9MB on every fresh context, competing
    // with the first navigation. Nothing here tests offline support.
    serviceWorkers: "block",
  },
  projects: [
    // Signs each fixture user in and saves the session (auth.setup.ts); specs
    // pick one with `test.use({ storageState })`.
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
  // The suite always serves the app itself, proxying /api and /ws to
  // E2E_DEV_PROXY_TARGET. CI serves the static build from its own workflow
  // step: the dev server force-reloads on newly discovered dependencies, which
  // wipes a test mid-way. Locally the dev server picks up code changes, and
  // `login()` retries to absorb that reload.
  webServer: {
    command: isCI
      ? `npm run preview -- --port ${PORT} --strictPort --host 127.0.0.1`
      : `npm run dev -- --port ${PORT} --strictPort --host 127.0.0.1`,
    url: ORIGIN,
    env: webServerEnv(env),
    reuseExistingServer: false,
    timeout: isCI ? 30_000 : 180_000,
    stdout: "pipe",
    stderr: "pipe",
  },
});
