import type { Page } from "@playwright/test";
import { loginForm, signedInUser } from "./auth";
import { expect } from "./test";

/** `page.goto` that also waits for `/api/permissions/me`, before which even an
 *  admin sees every gated control hidden. */
export async function gotoHydrated(page: Page, path: string) {
  // Armed before page.goto, so the test's timeout bounds these waits: an
  // action timeout would count the page load against them.
  const hydrated = page.waitForResponse(
    (r) => r.url().includes("/api/permissions/me"),
    { timeout: 0 },
  );
  await page.goto(path);
  // A rejected session lands on /login, which never requests permissions.
  const loginShown = loginForm(page).waitFor({ timeout: 0 });
  const response = await Promise.race([hydrated, loginShown.then(() => null)]);
  if (!response) {
    throw new Error(
      `Opened ${path} but landed on the login page: the backend rejected this test's saved session.`,
    );
  }
  if (!response.ok()) {
    throw new Error(
      `Permissions didn't load (GET /api/permissions/me returned ${response.status()}). The backend most likely rejected this test's saved session.`,
    );
  }
  // Renders once the auth store holds a user: the app shell is ready.
  await expect(signedInUser(page)).toBeVisible();
}

/** Open the first platform on the platforms index. */
export async function gotoFirstPlatform(page: Page) {
  await gotoHydrated(page, "/platforms");
  const platform = page.locator('a[href^="/platform/"]').first();
  await expect(
    platform,
    "No platform with games on /platforms: the site's library is empty or unscanned",
  ).toBeVisible();
  await platform.click();
  await expect(page).toHaveURL(/\/platform\/\d+/);
}

/** Open the first game of the first platform. */
export async function gotoFirstRom(page: Page) {
  await gotoFirstPlatform(page);
  const game = page.locator('a.r-gc[href^="/rom/"]').first();
  await expect(game, "The first platform shows no games").toBeVisible();
  await game.click();
  await expect(page).toHaveURL(/\/rom\/\d+/);
}

/** Open the account menu and follow its Profile link (route `/user/:user`). */
export async function gotoOwnProfile(page: Page) {
  await gotoHydrated(page, "/");
  await page.locator("[data-user-menu-trigger]").click();
  await page.getByRole("menuitem", { name: "Profile" }).click();
  await expect(page).toHaveURL(/\/user\/\d+/);
}
