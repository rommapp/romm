# E2E suite rules

- **Environment access lives in `e2e-environment.ts`.** Never read `process.env`, `import.meta.env` or a `.env` file in specs, `*.setup.ts` or `fixtures/`. Only `playwright.config.ts` may read `process.env` directly.
- **One backend, one URL.** The suite targets whatever `E2E_DEV_PROXY_TARGET` points at and serves its own frontend. Don't add Docker, a second target, or anything that assumes the backend runs on this machine.
- **New variable?** In the same change: add it to `E2EEnv` and `EXPECTED`, validate it in `readE2EEnv()` (push to `problems`, name the variable, never its value), document it in `.env.example`, and add it to `.github/workflows/e2e.yml` if CI needs it. No defaults in the parser: a missing value is an error.
- **Tests get the environment from their arguments:** `async ({ page, e2eEnv }) => ...`, with `test` and `expect` from `./fixtures/test`. ESLint enforces both. `import type { E2EEnv }` is fine. Helpers in `fixtures/` take values as parameters.
- **Prefer Playwright's own tools over custom scripts.** Recording, debugging, reports and traces come from the Playwright CLI and the VS Code extension; document the native way in the README.
- **Recorded code is a draft.** Before committing, give it real assertions, replace CSS-path and `nth()` selectors with roles and labels, and run it.
- **Timeouts:** don't add hard-coded ones that would outlive a debug session; the config sets every timeout to 0 when a debugger is attached. A test that genuinely needs longer leaves a debug session's 0 alone, as `auth.setup.ts` does.
- **Fail on the cause, not on a timeout.**
  - The automatic guard in `fixtures/test` fails a test the moment an `/api` call returns 5xx or the app throws. Opt out only in a test that triggers one on purpose, with `test.use({ failOnAppErrors: false })` and a comment saying why.
  - When a helper waits for a response, accept any status, then check it and throw a message naming the method, path and status, as `gotoHydrated()` does. Never filter on `status() === 200` inside `waitForResponse`.
  - Retry only what's transient (dev-server reloads). A server answer is final: throw at once, as `login()` does.
  - Don't paper over slowness with longer timeouts or `waitForTimeout`; find the event to wait for.
  - Observe the app's own traffic; don't call the API from tests.
- **Saved sessions in `e2e/.auth/` are reused across runs.** `auth.setup.ts` checks each one through the UI (`isSessionValid()`) and signs in afresh only when that fails. Keep that check UI-only.
- **`login.spec.ts` must start signed out,** via its explicit empty `storageState`.
- **Target devices live in `src/v2/devices.ts`,** the single home for Storybook's viewports and the device projects. A test joins the device sweep with `{ tag: "@devices" }`; keep that for behaviour that depends on size, touch or gamepad input, since each tagged test runs six more times.
- **Lint rules for e2e live in `frontend/eslint.e2e.config.js`,** never inline in `eslint.config.js`. A rule that's wrong for tests gets a named exception there with a one-line reason and the narrowest `files` glob, not an `eslint-disable` comment.
