import { ROLES, STORAGE_STATE } from "../../support/auth";
import { gotoOwnProfile } from "../../support/navigation";
import { expect, test } from "../../support/test";

// A self-edit can't change the role, so the profile shows it read-only (#3954).
for (const role of ROLES) {
  test.describe(
    `Profile page role field (${role})`,
    { tag: "@page:user-profile" },
    () => {
      test.use({ storageState: STORAGE_STATE[role] });

      test("gets no editable role control", async ({ page }) => {
        await gotoOwnProfile(page);

        // The editable rows that SHOULD be there, so a blank page can't pass.
        await expect(
          page.getByRole("textbox", { name: "Email" }),
        ).toBeVisible();

        // No role row, and no select (RSelect's listbox trigger) on the page.
        const main = page.getByRole("main");
        await expect(main.getByText("Role", { exact: true })).toHaveCount(0);
        await expect(main.locator('[aria-haspopup="listbox"]')).toHaveCount(0);
      });
    },
  );
}

test.describe("Profile page role chip", { tag: "@page:user-profile" }, () => {
  test.use({ storageState: STORAGE_STATE.viewer });

  test("still shows the role read-only", async ({ page }) => {
    await gotoOwnProfile(page);

    // The identity row still shows the role the picker no longer edits.
    const chip = page.locator(".r-v2-profile__role-tag");
    await expect(chip).toBeVisible();
    await expect(chip).toHaveText(/user/i);
  });
});
