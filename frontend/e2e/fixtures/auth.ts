import { expect, type Page } from "@playwright/test";

// Fixture accounts seeded by `backend/tools/seed_e2e_users.py`. `viewer` sits in
// the "Viewer (legacy)" group: library read plus own collections/assets, and no
// ROM write grant. `admin` is role=admin, so `useCan` short-circuits to true and
// every gated affordance must be present -- which is what makes these specs a
// two-sided check rather than "the button is missing".
export const USERS = {
  admin: process.env.E2E_ADMIN_USERNAME ?? "e2e_admin",
  viewer: process.env.E2E_VIEWER_USERNAME ?? "e2e_viewer",
} as const;

export const PASSWORD = process.env.E2E_PASSWORD ?? "e2e-Passw0rd!";

export type Role = keyof typeof USERS;

/** Log in through the real form and wait for the app shell to take over. */
export async function login(page: Page, role: Role) {
  await page.goto("/login");
  await page.fill('input[name="username"]', USERS[role]);
  await page.fill('input[name="password"]', PASSWORD);
  await page.click('button[type="submit"]');
  // The router replaces /login on success; a failed login leaves us here with a
  // snackbar, so assert the navigation rather than a fixed timeout.
  await expect(page).not.toHaveURL(/\/login/, { timeout: 15_000 });
}

/** Navigate to the logged-in user's own profile page (route `/user/:user`). */
export async function gotoOwnProfile(page: Page) {
  const res = await page.request.get("/api/users/me");
  expect(res.ok(), "could not resolve the current user").toBe(true);
  const me = await res.json();
  await page.goto(`/user/${me.id}`);
  return me;
}

/** Navigate to the first ROM of the first non-empty platform. */
export async function gotoFirstRom(page: Page) {
  const res = await page.request.get("/api/roms?limit=1&order_by=name");
  expect(res.ok(), "could not list ROMs -- is the dev library populated?").toBe(
    true,
  );
  const body = await res.json();
  const rom = body.items?.[0];
  expect(rom, "the dev library has no ROMs to test against").toBeTruthy();
  await page.goto(`/rom/${rom.id}`);
  return rom;
}

/** Open the ⋯ more-actions menu and return the teleported panel locator. */
export async function openMoreMenu(page: Page) {
  await page.getByRole("button", { name: "More actions" }).first().click();
  const panel = page.locator('[role="menu"]');
  await expect(panel).toBeVisible();
  return panel;
}

/** Visible labels of every item in an open menu panel, in DOM order. */
export async function menuLabels(page: Page): Promise<string[]> {
  return page.locator('[role="menu"] .r-menu-item__label').allInnerTexts();
}

/** Force the v2 UI and a known theme before the app boots.
 *  vueuse's `useLocalStorage` uses the string serializer for string refs, so
 *  these are stored raw -- NOT JSON-quoted. */
export async function seedUiState(page: Page, theme: "dark" | "light") {
  await page.addInitScript(
    ([t]) => {
      localStorage.setItem("settings.uiVersion", "v2");
      localStorage.setItem("settings.theme", t);
    },
    [theme],
  );
}
