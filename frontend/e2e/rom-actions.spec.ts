import { expect, test } from "@playwright/test";
import {
  gotoFirstRom,
  menuLabels,
  openMoreMenu,
  seedUiState,
  STORAGE_STATE,
} from "./fixtures/auth";

// Regression cover for #3954: the ⋯ menu offered Match / Refresh metadata /
// Edit / Delete to users with no ROM write grant. Those endpoints gate on
// ROMS_WRITE, so the click 403'd and the axios interceptor turned that into a
// logout -- the "page reloads back to the login page" in the bug report.
//
// Sessions come from auth.setup.ts; see login.spec.ts for the form itself.
const WRITE_ACTIONS = [
  "Match ROM",
  "Refresh metadata",
  "Edit",
  "Delete",
] as const;

test.describe("ROM more-actions menu (read-only user)", () => {
  test.use({ storageState: STORAGE_STATE.viewer });

  test("is offered no write or destructive action", async ({ page }) => {
    await seedUiState(page, "dark");
    await gotoFirstRom(page);
    await openMoreMenu(page);

    const labels = await menuLabels(page);
    for (const action of WRITE_ACTIONS) {
      expect(labels, `"${action}" must not be offered`).not.toContain(action);
    }
    // The actions they CAN perform are still there -- otherwise this spec would
    // also pass against a menu that failed to render at all.
    expect(labels).toContain("Download");
    expect(labels).toContain("Add to favourites");
  });

  test("has no trailing separator", async ({ page }) => {
    await seedUiState(page, "dark");
    await gotoFirstRom(page);
    const panel = await openMoreMenu(page);

    // Hiding the metadata + destructive groups must hide their leading dividers
    // too, or the menu ends in stray rules. One divider survives: the split
    // between the primary and per-user groups.
    await expect(panel.locator('[role="separator"]')).toHaveCount(1);

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
    await seedUiState(page, "light");
    await gotoFirstRom(page);
    const panel = await openMoreMenu(page);

    await expect(panel).toBeVisible();
    const labels = await menuLabels(page);
    expect(labels).not.toContain("Delete");
    expect(labels.length).toBeGreaterThan(0);
  });
});

test.describe("ROM more-actions menu (admin)", () => {
  test.use({ storageState: STORAGE_STATE.admin });

  test("still gets every action", async ({ page }) => {
    await seedUiState(page, "dark");
    await gotoFirstRom(page);
    const panel = await openMoreMenu(page);

    // `expect.poll` rather than a one-shot `menuLabels()` read: the menu is
    // reactive, so items appear as grants resolve. Snapshotting the array once
    // can capture the pre-grant menu and report a permissions bug that isn't.
    for (const action of WRITE_ACTIONS) {
      await expect
        .poll(() => menuLabels(page), {
          message: `"${action}" must still be offered to admins`,
        })
        .toContain(action);
    }
    // Primary | per-user | metadata | destructive => three dividers.
    await expect(panel.locator('[role="separator"]')).toHaveCount(3);
  });
});
