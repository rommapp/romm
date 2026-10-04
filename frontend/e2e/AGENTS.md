# E2E suite rules

- **Layout:** tests go in `specs/` and nothing else does, one folder per page named after its `PAGES` key in kebab case (`specs/game-details/`), each file named after what it checks. Specs that aren't about one page go in a folder named for their area, such as `specs/auth/`. Setup projects and the preflight go in `setup/`, fixtures and helpers in `support/`, and every generated file under `.output/`, through the paths in `support/output.ts`.
- **Every signed-in page is in `PAGES` in `specs/loads.spec.ts`,** which checks it loads with every response 2xx, and that a viewer gets the 404 on `adminOnly` pages. A new page gets an entry there. Tag each top-level `describe` of a page's other specs with its key, `{ tag: "@page:gameDetails" }`.
- **Environment access lives in `e2e-environment.ts`.** Never read `process.env`, `import.meta.env` or a `.env` file in specs, `setup/` or `support/`. Only `playwright.config.ts` may read `process.env` directly.
- **One site, one URL.** The suite tests whatever `E2E_BASE_URL` serves. Unset, the config's `webServer` starts the app (the dev server locally, the static build in CI); that is the only server it starts. Don't add Docker or a second target.
- **New variable?** In the same change: add it to `E2EEnv` (and `DEFAULTS` if `npm run test:e2e` should work without it), read it in `readE2EEnv()` (push malformed values to `problems`, naming the variable, never its value), document it in `.env.example`, and add it to `.github/workflows/e2e.yml` if CI needs it.
- **Tests get the environment from their arguments:** `async ({ page, e2eEnv }) => ...`, with `test` and `expect` from `support/test.ts`. ESLint enforces both. `import type { E2EEnv }` is fine. Helpers in `support/` take values as parameters.
- **Prefer Playwright's own tools over custom scripts.** Recording, debugging, reports and traces come from the Playwright CLI and the VS Code extension; document the native way in the README.
- **Recorded code is a draft.** Before committing, give it real assertions, replace CSS-path and `nth()` selectors with roles and labels, and run it.
- **Timeouts:** don't add hard-coded ones that would outlive a debug session; the config sets every timeout to 0 when a debugger is attached. A test that genuinely needs longer calls `test.slow()`, which leaves a debug session's 0 alone, as `auth.setup.ts` does.
- **Fail on the cause, not on a timeout.**
  - The automatic guard in `support/test.ts` fails a test the moment an `/api` call returns 5xx or the app throws. Opt out only in a test that triggers one on purpose, with `test.use({ failOnAppErrors: false })` and a comment saying why.
  - When a helper waits for a response, accept any status, then check it and throw a message naming the method, path and status, as `gotoHydrated()` does. Never filter on `status() === 200` inside `waitForResponse`.
  - Retry only what's transient, with Playwright's own `retries`: the `setup` project retries sign-in, which a dev-server reload can interrupt.
  - Don't paper over slowness with longer timeouts or `waitForTimeout`; find the event to wait for.
  - Observe the app's own traffic; don't call the API from tests (ESLint enforces it). `global-setup.ts` is the one exception: a preflight that runs before any test.
- **Every run signs in afresh.** `auth.setup.ts` saves each account's session to `e2e/.output/auth/` for that run's specs.
- **`login.spec.ts` must start signed out,** via its explicit empty `storageState`.
- **Lint rules for e2e live in `frontend/eslint.e2e.config.js`,** never inline in `eslint.config.js`. A rule that's wrong for tests gets a named exception there with a one-line reason and the narrowest `files` glob, not an `eslint-disable` comment.
