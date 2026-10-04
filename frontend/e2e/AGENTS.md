# E2E suite rules

- **Layout:** tests go in `specs/` and nothing else does, one folder per page named after its route name in `src/plugins/routeNames.ts` (`specs/rom/`), each file named after what it checks. Specs that aren't about one page go in a folder named for their area, such as `specs/auth/`. Setup projects go in `setup/`, fixtures and helpers in `support/`, and every generated file under `.output/`, through the paths in `support/output.ts`.
- **Every route is in `PAGES` in `specs/loads.spec.ts`,** keyed by route name, so a new route fails the typecheck until it gets an entry: a page to open, which must load for each role allowed on it with every response 2xx (and give a viewer the 404 page when `adminOnly`), or a `skip` with the reason. Tag each top-level `describe` of a page's other specs with its route name, `{ tag: "@page:rom" }`.
- **Each variable has one home.** `playwright.config.ts` loads `e2e/.env` and reads `E2E_BASE_URL`; `support/auth.ts` reads the account variables into `ACCOUNTS`. Specs read neither `process.env` nor `.env`: they take `ACCOUNTS`, or Playwright's `baseURL` fixture. A new variable gets a default that works against a seeded dev backend, and a line in `.env.example`.
- **One site, one URL.** The suite tests whatever `E2E_BASE_URL` serves. Unset, the config's `webServer` starts the app (the dev server locally, the static build in CI); that is the only server it starts. Don't add Docker or a second target.
- **Import `test` and `expect` from `support/test.ts`,** so the app-error guard applies. ESLint enforces it.
- **Prefer Playwright's own tools over custom scripts.** Recording, debugging, reports and traces come from the Playwright CLI and the VS Code extension; document the native way in the README.
- **Recorded code is a draft.** Before committing, give it real assertions, replace CSS-path and `nth()` selectors with roles and labels, and run it.
- **Timeouts:** don't add hard-coded ones that would outlive a debug session; the config sets every timeout to 0 when a debugger is attached. A test that genuinely needs longer calls `test.slow()`, which leaves a debug session's 0 alone, as `auth.setup.ts` does.
- **Fail on the cause, not on a timeout.**
  - The automatic guard in `support/test.ts` fails a test the moment an `/api` call returns 5xx or the app throws.
  - When a helper waits for a response, accept any status, then check it and throw a message naming the method, path and status, as `gotoHydrated()` does. Never filter on `status() === 200` inside `waitForResponse`.
  - Retry only what's transient, with Playwright's own `retries`: the `setup` project retries sign-in, which a dev-server reload can interrupt.
  - Don't paper over slowness with longer timeouts or `waitForTimeout`; find the event to wait for.
  - Observe the app's own traffic; don't call the API from tests (ESLint enforces it).
- **Every run signs in afresh.** `auth.setup.ts` saves each account's session to `e2e/.output/auth/` for that run's specs.
- **Pick a theme with `colorScheme`** (`page.emulateMedia()` or `test.use()`), never by writing `settings.theme`: the app syncs UI settings to the account, so a written theme leaks into every later sign-in. The suite's stored theme is always "auto".
- **`login.spec.ts` must start signed out,** via its explicit empty `storageState`.
- **Lint rules for e2e live in `frontend/eslint.e2e.config.js`,** never inline in `eslint.config.js`. A rule that's wrong for tests gets a named exception there with a one-line reason and the narrowest `files` glob, not an `eslint-disable` comment.
