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

/** Log in through the real form and wait for the app shell to take over.
 *
 *  Everything is scoped to `form.r-v2-login-form`. The reset-password form is
 *  rendered alongside it (collapsed, not unmounted) and has its own submit
 *  button and fields, so unscoped `button[type="submit"]` / `input[name=...]`
 *  selectors match two elements and blow up on strict mode -- intermittently,
 *  depending on whether that form has mounted yet. */
export async function login(
  page: Page,
  role: Role,
  {
    timeout = 25_000,
    attempts = 3,
  }: { timeout?: number; attempts?: number } = {},
) {
  // Retried because the Vite dev server force-reloads the page when it
  // discovers a new dependency to pre-bundle ("optimized dependencies changed.
  // reloading"). That wipes the half-filled form and the submit never lands, so
  // the login silently does nothing. It's an infrastructure event, not an app
  // failure, and it mostly happens on the first navigations of a cold server.
  // Bad credentials still fail, just after `attempts` tries.
  let lastError: unknown;
  for (let attempt = 1; attempt <= attempts; attempt++) {
    try {
      await page.goto("/login");
      const form = page.locator("form.r-v2-login-form");
      await form.locator('input[name="username"]').fill(USERS[role]);
      await form.locator('input[name="password"]').fill(PASSWORD);
      await form.locator('button[type="submit"]').click();
      // Assert a marker that only exists once authenticated (the app bar's user
      // name) rather than just "the URL is no longer /login" -- the latter goes
      // true mid-transition and says nothing about the session.
      await expect(page.locator(".r-v2-user__name")).toHaveText(USERS[role], {
        timeout,
      });
      await expect(page).not.toHaveURL(/\/login/);
      return;
    } catch (error) {
      lastError = error;
    }
  }
  throw lastError;
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
