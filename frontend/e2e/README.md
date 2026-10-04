# End-to-end tests (Playwright)

The real app, in a real browser, against a real backend. Use these for behaviour that only shows up once everything is assembled; Vitest covers components in isolation.

## Run it

You need a backend with games in its library and two accounts: an admin, and a non-admin in the Viewer group. On a throwaway dev backend, the seed script creates both (run it from the repo root). Never run it against a real server; it resets those accounts' passwords.

```bash
uv run python .github/scripts/seed_e2e_users.py
```

Then, from `frontend/`:

```bash
npm run test:e2e
```

That starts `npm run dev` (or reuses the one already running on 3000), which proxies to the backend named by `DEV_PORT` or `DEV_PROXY_TARGET` in `.env`. To point the suite at another site or other accounts, set the variables from `e2e/.env.example` in your shell or in `e2e/.env`. A malformed value stops the run before anything starts, listing every problem at once.

Install the recommended VS Code extension, **Playwright Test for VS Code**. Most recipes below start from its panel in the Testing sidebar.

## Recipes

### Write a new test by clicking

Create the file, leave the cursor inside the test, and click **Record at cursor** in the Playwright panel:

```ts
// e2e/specs/favorite-a-game.spec.ts
import { STORAGE_STATE } from "../support/auth";
import { expect, test } from "../support/test";

test.use({ storageState: STORAGE_STATE.admin });

test("favorites a game", async ({ page }) => {
  await page.goto("/");
  // cursor here
});
```

A browser opens, already signed in, and every click is written into the file. Use the recorder's assert buttons for what should be true afterwards, then replace any `nth()` or CSS-path selectors with roles and labels.

### Watch a test run

Tick **Show browser** in the Playwright panel and run any test. From a terminal:

```bash
npx playwright test --headed --workers 1
```

### Find out why a test failed

```bash
npx playwright test --ui    # click a step to see the page, network and console at that moment
npm run test:e2e:report    # the last run's failures, with traces
```

For a CI failure, download the `playwright-report` artifact from the workflow run, unzip it, and run `npx playwright show-report <unzipped>/report`.

### Stop on a line

Set a breakpoint, right-click the test's gutter arrow, and choose **Debug Test**. Timeouts switch off while a debugger is attached, so take your time.

### Poke at the page mid-test

```ts
await page.pause();
```

```bash
npx playwright test --debug e2e/specs/game-details/actions-menu.spec.ts
```

The Inspector steps one action at a time, tries locators live, and records more steps. ESLint refuses a committed `page.pause()`.

### Find a selector

**Pick locator** in the Playwright panel, then click the element. The locator is copied for you.

### Debug the Vue app itself

Run headed, press F12 in the test browser, and put `debugger;` in any `.vue` file. It pauses there, with the real source files.

### Test as the viewer

```ts
test.use({ storageState: STORAGE_STATE.viewer });
```

Need the credentials themselves? Take them from the test arguments:

```ts
test("rejects a wrong password", async ({ page, e2eEnv }) => {
  const { username } = accountFor(e2eEnv, "viewer");
});
```

### Test Explorer shows no tests

The extension lists tests by loading `playwright.config.ts`, which validates the `E2E_*` variables first. If that fails, the panel stays empty. See why:

```bash
npx playwright test --list
```

Fix what it reports, then click **Refresh Tests** in the Testing sidebar.

### Run one file, one test, or one page

```bash
npm run test:e2e -- e2e/specs/auth/login.spec.ts
npm run test:e2e -- -g "rejects a wrong password"
npm run test:e2e -- --grep "@page:gameDetails\b"   # every test for one page (the keys of PAGES in specs/loads.spec.ts)
```

### Test another site

Set `E2E_BASE_URL` (in the shell or `e2e/.env`), and use accounts that exist there:

```ini
E2E_BASE_URL=https://romm.example.com
```

The specs follow this branch's UI, so a site on another version fails where the two differ. A released site (5.3.1, say) lacks endpoints added on master since, and `loads.spec.ts` reports each as a 404. For a full pass, run a backend from this checkout (`uv run main.py`) and leave `E2E_BASE_URL` unset.

To test a production build of this branch, serve it first: `npm run build:preview && npm run preview` (`build:preview` adds `frontend/assets`, which Vite leaves out and the Docker image copies in), then set `E2E_BASE_URL=http://localhost:4173`.

## How it's wired

```text
e2e/
  specs/      the tests, and only tests, one folder per page
    loads.spec.ts   every page opens with every response 2xx
  setup/      sign-in, run before the specs
  support/    fixtures, helpers, environment and output paths
  .output/    generated and gitignored; delete it to reset
    auth/       saved sessions
    specs/      results/ (traces, screenshots) and report/ (HTML)
```

- **Environment:** every `E2E_*` variable comes from the shell, then `e2e/.env`, then a default that matches the seed script. CI sets them in `.github/workflows/e2e.yml`.
- **Server:** with `E2E_BASE_URL` unset, the config's `webServer` starts one: `npm run dev` locally (reusing one already running), the static build under `vite preview` in CI. Otherwise it tests that URL as served.
- **Sign-in:** `setup/auth.setup.ts` signs each account in at the start of every run and saves the session for the specs. `login.spec.ts` is the only spec that drives the login form.
- **Timeouts:** 10s per test locally, so failures are fast; CI keeps longer ones. They switch off while debugging.
- **App errors:** if an `/api` call returns 5xx or the app throws, the test fails at once and names the request (for example `GET /api/roms returned 500`) instead of timing out on an element.
- **Output:** everything the suite writes goes under `.output/`, through the paths in `support/output.ts`.
- **Checks:** `npm run typecheck` covers the suite (`typecheck:e2e` runs it alone), and lint rules live in `eslint.e2e.config.js`.
- **Changing the suite itself:** see [AGENTS.md](AGENTS.md).
