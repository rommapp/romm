# End-to-end tests (Playwright)

The real app, in a real browser, against a real backend. Use these for behaviour that only shows up once everything is assembled; Vitest covers components in isolation.

## Run it

You need one running RomM site to point at, with games in its library and two accounts: an admin, and a non-admin in the Viewer group. The suite starts no server; it tests whatever `E2E_BASE_URL` serves.

From `frontend/`, with the site up (for example `npm run dev`, which serves on 3000 and proxies to the backend named by `DEV_PORT` or `DEV_PROXY_TARGET` in `.env`):

```bash
cp e2e/.env.example e2e/.env
npm run test:e2e
```

The example works as-is against `npm run dev` with the seeded accounts below. For any other site, change `E2E_BASE_URL` and the accounts. If anything in `e2e/.env` is missing or malformed, the run stops before starting anything and lists every problem at once.

On a throwaway dev backend, the seed script creates the two accounts from `.env.example` (run it from the repo root). Never run it against a real server; it resets those accounts' passwords.

```bash
uv run python .github/scripts/seed_e2e_users.py
```

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

The extension lists tests by loading `playwright.config.ts`, which validates `e2e/.env` first. If that fails, the panel stays empty. See why:

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

Change `E2E_BASE_URL` in `e2e/.env`, and use accounts that exist there:

```ini
E2E_BASE_URL=https://romm.example.com
```

The specs follow this branch's UI, so a site on another version fails where the two differ. A released site (5.3.1, say) lacks endpoints added on master since, and `loads.spec.ts` reports each as a 404; the preflight prints the site's version so this is easy to spot. For a full pass, run a backend from this checkout (`uv run main.py`) behind `npm run dev`.

To test a production build of this branch, serve it first: `npm run build && npm run preview`, then set `E2E_BASE_URL=http://localhost:4173`.

### Sign in again

Sessions are saved in `e2e/.output/auth/` and reused, after a check that each still signs the right account in. One that doesn't (expired, another site, another account) is replaced automatically. To force a fresh sign-in anyway:

```bash
rm -r e2e/.output/auth    # PowerShell: Remove-Item -Recurse e2e/.output/auth
```

## How it's wired

```text
e2e/
  specs/      the tests, and only tests, one folder per page
    loads.spec.ts   every page opens with every response 2xx
  setup/      preflight and sign-in, run before the specs
  support/    fixtures, helpers, environment and output paths
  .output/    generated and gitignored; delete it to reset
    auth/       saved sessions
    specs/      results/ (traces, screenshots) and report/ (HTML)
```

- **`e2e/.env`:** required locally, and the only source of `E2E_*` variables. CI sets the same variables in `.github/workflows/e2e.yml`.
- **Server:** the suite starts none. It tests `E2E_BASE_URL` as served; CI serves the static build with `vite preview` and points the suite at it.
- **Preflight:** `setup/global-setup.ts` runs first and checks, in about a second, that the backend answers, both accounts sign in and can read ROMs, and the library has a game. One error lists every problem.
- **Sign-in:** `setup/auth.setup.ts` signs each account in once and saves the session. `login.spec.ts` is the only spec that drives the login form.
- **Timeouts:** 10s per test locally, so failures are fast; CI keeps longer ones. They switch off while debugging.
- **App errors:** if an `/api` call returns 5xx or the app throws, the test fails at once and names the request (for example `GET /api/roms returned 500`) instead of timing out on an element.
- **Output:** everything the suite writes goes under `.output/`, through the paths in `support/output.ts`.
- **Checks:** `npm run typecheck:e2e` for the specs, `npm run typecheck:scripts` for `playwright.config.ts`, and lint rules in `eslint.e2e.config.js`.
- **Changing the suite itself:** see [AGENTS.md](AGENTS.md).
