# End-to-end tests (Playwright)

The real app, in a real browser, against a real backend. Use these for behaviour that only shows up once everything is assembled; Vitest covers components in isolation.

## Run it

You need one RomM backend to point at, with games in its library and two accounts: an admin, and a non-admin in the Viewer group. Any reachable instance works: local, on your LAN, or remote. The suite serves its own frontend and proxies `/api` and `/ws` to it.

From `frontend/`:

```bash
cp e2e/.env.example e2e/.env   # then set E2E_DEV_PROXY_TARGET and the two accounts
npm run test:e2e
```

If anything in `e2e/.env` is missing or malformed, the run stops before starting anything and lists every problem at once.

On a throwaway dev backend, the seed script creates the two accounts from `.env.example` (run it from the repo root). Never run it against a real server; it resets those accounts' passwords.

```bash
uv run python .github/scripts/seed_e2e_users.py
```

Install the recommended VS Code extension, **Playwright Test for VS Code**. Most recipes below start from its panel in the Testing sidebar.

## Recipes

### Write a new test by clicking

Create the file, leave the cursor inside the test, and click **Record at cursor** in the Playwright panel:

```ts
// e2e/favorite-a-game.spec.ts
import { STORAGE_STATE } from "./fixtures/auth";
import { expect, test } from "./fixtures/test";

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
npm run test:e2e:headed
```

### Find out why a test failed

```bash
npm run test:e2e:ui       # click a step to see the page, network and console at that moment
npm run test:e2e:report   # the last run's failures, with traces
```

For a CI failure, download the `playwright-report` artifact from the workflow run and open it the same way.

### Stop on a line

Set a breakpoint, right-click the test's gutter arrow, and choose **Debug Test**. Timeouts switch off while a debugger is attached, so take your time.

### Poke at the page mid-test

```ts
await page.pause();
```

```bash
npm run test:e2e:debug -- e2e/rom-actions.spec.ts
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

### Test on a phone, tablet or handheld

Tag the test, and it also runs on six target devices: RomM phone, tablet and desktop sizes, the Steam Deck, and both AYN Thor screens. The handhelds start in gamepad mode.

```ts
test("opens the game page", { tag: "@devices" }, async ({ page }) => {
  await gotoFirstRom(page);
});
```

```bash
npm run test:e2e -- --project="steam*"
```

In VS Code, tick the device's project in the Playwright panel and **Show browser**; it opens at that device's size. More in [DEVICES.md](DEVICES.md).

### Run one file, or one test

```bash
npm run test:e2e -- e2e/login.spec.ts
npm run test:e2e -- -g "rejects a wrong password"
```

### Test against another backend

Change `E2E_DEV_PROXY_TARGET` in `e2e/.env`, and use accounts that exist there:

```ini
E2E_DEV_PROXY_TARGET=https://romm.example.com
```

### Sign in again

Sessions are saved in `e2e/.auth/` and reused, after a check that each still signs the right account in. One that doesn't (expired, another backend, another account) is replaced automatically. To force a fresh sign-in anyway:

```bash
rm -r e2e/.auth    # PowerShell: Remove-Item -Recurse e2e/.auth
```

## How it's wired

- **`e2e/.env`:** required locally, and the only source of `E2E_*` variables. CI sets the same variables in `.github/workflows/e2e.yml`.
- **Server:** the suite starts its own on port 3100, proxying to `E2E_DEV_PROXY_TARGET`. That's the dev server locally, and a static build in CI.
- **Sign-in:** `auth.setup.ts` signs each account in once and saves the session. `login.spec.ts` is the only spec that drives the login form.
- **Timeouts:** 10s per test, so failures are fast. They switch off while debugging.
- **App errors:** if an `/api` call returns 5xx or the app throws, the test fails at once and names the request (for example `GET /api/roms returned 500`) instead of timing out on an element.
- **Checks:** `npm run typecheck:e2e` for the specs, `npm run typecheck:scripts` for `playwright.config.ts`, and lint rules in `eslint.e2e.config.js`.
- **Changing the suite itself:** see [AGENTS.md](AGENTS.md).
