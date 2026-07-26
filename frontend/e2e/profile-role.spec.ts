import { expect, test } from "@playwright/test";
import { gotoOwnProfile, login, seedUiState } from "./fixtures/auth";

// Regression cover for #3954: the profile page shipped an editable role picker,
// but `update_user` ignores `role` on a self-edit. Saving reported success and
// then silently reverted on reload -- for admins as much as for regular users.
// The role is display-only now: the chip in the identity row.
test.describe("Profile page role field", () => {
  for (const role of ["viewer", "admin"] as const) {
    test(`${role} gets no editable role control`, async ({ page }) => {
      await seedUiState(page, "dark");
      await login(page, role);
      await gotoOwnProfile(page);

      // The editable rows that SHOULD be there, so a blank page can't pass.
      await expect(page.locator('input[type="email"]')).toBeVisible();

      // No role row in the Account Details form.
      const form = page.locator(".r-v2-section-stack");
      await expect(form.getByText("Role", { exact: true })).toHaveCount(0);
      // And no select rendered anywhere on the page.
      await expect(page.locator(".r-select")).toHaveCount(0);
    });
  }

  test("the role is still shown as a read-only chip", async ({ page }) => {
    await seedUiState(page, "dark");
    await login(page, "viewer");
    await gotoOwnProfile(page);

    // Identity row keeps the role visible -- removing the picker must not
    // remove the information.
    const chip = page.locator(".r-v2-profile__role-tag");
    await expect(chip).toBeVisible();
    await expect(chip).toHaveText(/user/i);
  });
});
