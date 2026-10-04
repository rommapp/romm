import type { Page } from "@playwright/test";
import { AUTH_DIR } from "./output";

const { env } = process;

// The seed script sets both accounts' password from E2E_PASSWORD.
const SEEDED_PASSWORD = env.E2E_PASSWORD || "e2e-Passw0rd!";

// The accounts every permission assertion is made against. The defaults are
// the ones .github/scripts/seed_e2e_users.py creates.
export const ACCOUNTS = {
  admin: {
    username: env.E2E_ADMIN_USERNAME || "e2e_admin",
    password: env.E2E_ADMIN_PASSWORD || SEEDED_PASSWORD,
  },
  viewer: {
    username: env.E2E_VIEWER_USERNAME || "e2e_viewer",
    password: env.E2E_VIEWER_PASSWORD || SEEDED_PASSWORD,
  },
};

export const ROLES = ["admin", "viewer"] as const;

export type Role = (typeof ROLES)[number];

/** Where auth.setup.ts saves each role's session (gitignored: live cookies). */
export const STORAGE_STATE: Record<Role, string> = {
  admin: `${AUTH_DIR}/admin.json`,
  viewer: `${AUTH_DIR}/viewer.json`,
};

/** Fill and submit the login form. Scoped to `form.r-v2-login-form`, since the
 *  collapsed reset-password form has its own fields and submit button. */
export async function fillLoginForm(
  page: Page,
  username: string,
  password: string,
) {
  const form = page.locator("form.r-v2-login-form");
  await form.locator('input[name="username"]').fill(username);
  await form.locator('input[name="password"]').fill(password);
  await form.locator('button[type="submit"]').click();
}

/** Force the v2 UI before the app boots, with the theme following the
 *  browser's `colorScheme`. The app syncs these settings to the user's
 *  account, so "auto" is the only theme the suite ever stores there. */
export async function seedUiState(page: Page) {
  await page.addInitScript(() => {
    // Init scripts also run in Chrome's own error page, which denies storage.
    if (!location.protocol.startsWith("http")) return;
    const seeded = { "settings.uiVersion": "v2", "settings.theme": "auto" };
    // The app only adopts an unscoped value when the signed-in user has no
    // `user:<id>:` copy, and a saved session carries one.
    for (const key of Object.keys(localStorage)) {
      const scoped = /^user:\d+:(.+)$/.exec(key)?.[1];
      if (scoped && Object.hasOwn(seeded, scoped)) localStorage.removeItem(key);
    }
    for (const [key, value] of Object.entries(seeded)) {
      localStorage.setItem(key, value);
    }
  });
}
