import type { Locator, Page } from "@playwright/test";
import { STORAGE_STATE } from "../../support/auth";
import { gotoFirstRom } from "../../support/navigation";
import { expect, test } from "../../support/test";

// A viewer's ⋯ menu offers no ROMS_WRITE action: the 403 it would hit logs
// them out (#3954).
const WRITE_ACTIONS = [
  "Match ROM",
  "Refresh metadata",
  "Edit",
  "Delete",
] as const;

/** Open the ⋯ more-actions menu and return its teleported panel. */
async function openMoreMenu(page: Page) {
  await page.getByRole("button", { name: "More actions" }).first().click();
  const panel = page.getByRole("menu");
  await expect(panel).toBeVisible();
  return panel;
}

/** Labels of the open menu's items, in DOM order. RMenuItem only sets the
 *  menuitem role on links; an action item stays a plain button. */
function menuLabels(panel: Locator): Promise<string[]> {
  return panel
    .getByRole("menuitem")
    .or(panel.getByRole("button"))
    .allInnerTexts();
}

test.describe(
  "ROM more-actions menu (read-only user)",
  { tag: "@page:rom" },
  () => {
    test.use({ storageState: STORAGE_STATE.viewer });

    test("is offered no write or destructive action", async ({ page }) => {
      await gotoFirstRom(page);
      const panel = await openMoreMenu(page);

      const labels = await menuLabels(panel);
      for (const action of WRITE_ACTIONS) {
        expect(labels, `"${action}" must not be offered`).not.toContain(action);
      }
      // Their own actions stay, so a menu that failed to render can't pass.
      expect(labels).toContain("Download");
      expect(labels).toContain("Add to favorites");
    });

    test("has no trailing separator", async ({ page }) => {
      await gotoFirstRom(page);
      const panel = await openMoreMenu(page);

      // Hidden groups take their leading dividers with them; only the one
      // between the primary and per-user groups remains.
      await expect(panel.getByRole("separator")).toHaveCount(1);

      // And the last thing in the panel is an item, not a rule.
      const lastChildIsSeparator = await panel.evaluate((el) => {
        const body = el.querySelector(".r-menu__body") ?? el;
        const kids = Array.from(body.children).filter(
          (c) => (c as HTMLElement).offsetParent !== null || c.clientHeight > 0,
        );
        const last = kids[kids.length - 1];
        return last?.getAttribute("role") === "separator";
      });
      expect(lastChildIsSeparator).toBe(false);
    });

    test("renders in light theme too", async ({ page }) => {
      await page.emulateMedia({ colorScheme: "light" });
      await gotoFirstRom(page);
      await expect(page.locator("html")).toHaveClass(/\br-v2-light\b/);
      const panel = await openMoreMenu(page);

      const labels = await menuLabels(panel);
      expect(labels).not.toContain("Delete");
      expect(labels.length).toBeGreaterThan(0);
    });
  },
);

test.describe("ROM more-actions menu (admin)", { tag: "@page:rom" }, () => {
  test.use({ storageState: STORAGE_STATE.admin });

  test("still gets every action", async ({ page }) => {
    await gotoFirstRom(page);
    const panel = await openMoreMenu(page);

    // Polled: items appear as grants resolve, so a single read can catch the
    // menu before they do.
    for (const action of WRITE_ACTIONS) {
      await expect
        .poll(() => menuLabels(panel), {
          message: `"${action}" must still be offered to admins`,
        })
        .toContain(action);
    }
    // Primary | per-user | metadata | destructive => three dividers.
    await expect(panel.getByRole("separator")).toHaveCount(3);
  });
});
