import { gotoOwnProfile, STORAGE_STATE } from "../../support/auth";
import { expect, test } from "../../support/test";

// A self-edit can't change the role, so the profile shows it read-only (#3954).
for (const role of ["viewer", "admin"] as const) {
  test.describe(
    `Profile page role field (${role})`,
    { tag: "@page:user-profile" },
    () => {
      test.use({ storageState: STORAGE_STATE[role] });

      test("gets no editable role control", async ({ page }) => {
        await gotoOwnProfile(page);

        // The editable rows that SHOULD be there, so a blank page can't pass.
        await expect(page.locator('input[type="email"]')).toBeVisible();

        // No role row in the Account Details form.
        const form = page.locator(".r-v2-section-stack");
        await expect(form.getByText("Role", { exact: true })).toHaveCount(0);
        // And no select rendered anywhere on the page.
        await expect(page.locator(".r-select")).toHaveCount(0);
      });
    },
  );
}

test.describe("Profile page role chip", { tag: "@page:user-profile" }, () => {
  test.use({ storageState: STORAGE_STATE.viewer });

  test("still shows the role read-only", async ({ page }) => {
    await gotoOwnProfile(page);

    // Identity row keeps the role visible -- removing the picker must not
    // remove the information.
    const chip = page.locator(".r-v2-profile__role-tag");
    await expect(chip).toBeVisible();
    await expect(chip).toHaveText(/user/i);
  });
});
