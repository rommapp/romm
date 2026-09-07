import { test as setup } from "@playwright/test";
import { login, seedUiState, STORAGE_STATE, USERS } from "./fixtures/auth";

// Runs once per role before the suite, as its own Playwright project (see
// `dependencies` in playwright.config.ts). Each saves the authenticated session
// -- cookies plus localStorage -- so the specs can start already logged in
// instead of driving the form 15 times over.
//
// The login FLOW itself is covered by login.spec.ts, which deliberately uses a
// fresh unauthenticated page. This file is plumbing: if it breaks, that spec is
// where the real diagnosis lives.
for (const role of Object.keys(USERS) as (keyof typeof USERS)[]) {
  setup(`authenticate as ${role}`, async ({ page }) => {
    // Bake the v2 flag into the saved state so every spec inherits it.
    await seedUiState(page, "dark");
    await login(page, role);
    await page.context().storageState({ path: STORAGE_STATE[role] });
  });
}
