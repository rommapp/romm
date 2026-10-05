import type { BrowserContextOptions, Locator, Page } from "@playwright/test";
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

export type Role = keyof typeof ACCOUNTS;

export const ROLES = Object.keys(ACCOUNTS) as Role[];

/** Where auth.setup.ts saves each role's session (gitignored: live cookies). */
export const STORAGE_STATE = Object.fromEntries(
  ROLES.map((role) => [role, `${AUTH_DIR}/${role}.json`]),
) as Record<Role, string>;

/** An empty session, for pages opened as a visitor who hasn't signed in. */
export const SIGNED_OUT: Exclude<
  BrowserContextOptions["storageState"],
  string | undefined
> = { cookies: [], origins: [] };

/** The login form's submit button. Roles skip the hidden reset-password form,
 *  which has a Username field of its own. */
export function loginButton(page: Page): Locator {
  return page.getByRole("button", { name: "Login", exact: true });
}

/** The app bar's account menu, labelled with the signed-in user's name (any
 *  user's when none is given). It reads "Guest" until the session loads. */
export function accountMenu(page: Page, username?: string): Locator {
  const user = username ? RegExp.escape(username) : "(?!Guest$).+";
  return page.getByRole("button", {
    name: new RegExp(`^Account menu for ${user}$`, "i"),
  });
}

/** Fill and submit the login form. */
export async function fillLoginForm(
  page: Page,
  username: string,
  password: string,
) {
  await page.getByRole("textbox", { name: "Username" }).fill(username);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await loginButton(page).click();
}

/** Force the v2 UI before the app boots, and the "auto" theme, so the
 *  browser's `colorScheme` picks it and the account never stores another. */
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
