import { defineConfig, devices } from "@playwright/test";
import { url as inspectorUrl } from "node:inspector";
import { readE2EEnv, webServerEnv } from "./e2e/e2e-environment";
import type { E2EOptions } from "./e2e/fixtures/test";
import { deviceProjectName, ROMM_DEVICES } from "./src/v2/devices";

// End-to-end suite: `npm run test:e2e`. Accounts and the backend under test
// come from e2e/.env (see e2e/.env.example); CI sets them in the workflow.
const env = readE2EEnv();

const isCI = env.CI;
// A test paused on a breakpoint must not be killed by the timeouts below.
const debugging = !!process.env.PWDEBUG || inspectorUrl() !== undefined;
// Off the default dev port, so the suite never collides with a `npm run dev`.
const PORT = 3100;
const ORIGIN = `http://127.0.0.1:${PORT}`;
// Local runs fail fast. CI keeps its established policy until per-test
// timings are measured. 0 means no timeout.
const TIMEOUTS = debugging
  ? { test: 0, expect: 0, action: 0, navigation: 0 }
  : isCI
    ? { test: 45_000, expect: 10_000, action: 15_000, navigation: 30_000 }
    : { test: 10_000, expect: 3_000, action: 5_000, navigation: 5_000 };

export default defineConfig<E2EOptions>({
  testDir: "./e2e",
  // Permission gating is global state on the server (the fixture users' grants),
  // so the specs read it rather than mutate it and are safe to parallelise.
  fullyParallel: true,
  forbidOnly: isCI,
  // Locally a failure shows on the first run; retries would hide it.
  retries: isCI ? 2 : 0,
  // Every worker hammers ONE server, so keep the pool small.
  workers: env.E2E_WORKERS ?? 2,
  // The HTML report holds each failure's trace: `npm run test:e2e:report`.
  reporter: [[isCI ? "github" : "list"], ["html", { open: "never" }]],
  // A test that genuinely needs longer uses `test.setTimeout`.
  timeout: TIMEOUTS.test,
  expect: { timeout: TIMEOUTS.expect },
  use: {
    baseURL: ORIGIN,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    actionTimeout: TIMEOUTS.action,
    navigationTimeout: TIMEOUTS.navigation,
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
    // One project per target device (src/v2/devices.ts), for tests tagged
    // `@devices` only. See e2e/DEVICES.md.
    ...Object.values(ROMM_DEVICES).map((device) => ({
      name: deviceProjectName(device),
      testIgnore: /.*\.setup\.ts/,
      grep: /@devices/,
      dependencies: ["setup"],
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: device.width, height: device.height },
        hasTouch: device.hasTouchHci,
        isMobile: device.type === "mobile",
        gamepad: device.hasGamepadHci,
      },
    })),
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
    // 3100 is the suite's own port, so locally reuse its server (e.g. the one
    // the VS Code extension keeps running). CI always starts fresh.
    reuseExistingServer: !isCI,
    timeout: 180_000,
    stdout: "pipe",
    stderr: "pipe",
  },
});
