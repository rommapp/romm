import { existsSync, rmSync } from "node:fs";
import {
  accountFor,
  isSessionValid,
  login,
  ROLES,
  seedUiState,
  STORAGE_STATE,
} from "./fixtures/auth";
import { test as setup } from "./fixtures/test";

// Signs each role in once before the suite (the `setup` project) and saves the
// session, so specs start authenticated. A saved session is reused while it
// still signs the right account in; otherwise it's replaced. login.spec.ts is
// where the login flow itself is tested.
for (const role of ROLES) {
  setup(`authenticate as ${role}`, async ({ browser, page, e2eEnv }) => {
    // The first load compiles the app on a cold dev server, so this test gets
    // at least 60s. A debug session's 0 is left alone.
    const budget = setup.info().timeout;
    if (budget > 0) setup.setTimeout(Math.max(budget, 60_000));
    const firstLoad = e2eEnv.CI ? 25_000 : 15_000;
    const account = accountFor(e2eEnv, role);
    const saved = STORAGE_STATE[role];
    const note = (description: string) =>
      setup.info().annotations.push({ type: "session", description });

    if (existsSync(saved)) {
      const valid = await isSessionValid(browser, {
        path: saved,
        username: account.username,
        baseURL: setup.info().project.use.baseURL,
        timeout: firstLoad,
      });
      if (valid) {
        note("Reused the saved session.");
        return;
      }
      rmSync(saved);
      note(
        "The saved session no longer signed this account in; signed in again.",
      );
    }

    // Bake the v2 flag into the saved state so every spec inherits it.
    await seedUiState(page, "dark");
    // CI serves a static build, so the dev server's reload retry isn't needed.
    await login(page, account, {
      timeout: firstLoad,
      attempts: e2eEnv.CI ? 1 : 3,
    });
    await page.context().storageState({ path: saved });
  });
}
