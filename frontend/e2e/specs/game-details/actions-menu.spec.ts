import {
  gotoFirstRom,
  menuLabels,
  openMoreMenu,
  seedUiState,
  STORAGE_STATE,
} from "../../support/auth";
import { expect, test } from "../../support/test";

// A viewer's ⋯ menu offers no ROMS_WRITE action: the 403 it would hit logs
// them out (#3954).
const WRITE_ACTIONS = [
  "Match ROM",
  "Refresh metadata",
  "Edit",
  "Delete",
] as const;

test.describe(
  "ROM more-actions menu (read-only user)",
  { tag: "@page:gameDetails" },
  () => {
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
      expect(labels).toContain("Add to favorites");
    });

    test("has no trailing separator", async ({ page }) => {
      await seedUiState(page, "dark");
      await gotoFirstRom(page);
      const panel = await openMoreMenu(page);

      // Hidden groups take their leading dividers with them; only the one
      // between the primary and per-user groups remains.
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
      await expect(page.locator("html")).toHaveClass(/\br-v2-light\b/);
      const panel = await openMoreMenu(page);

      await expect(panel).toBeVisible();
      const labels = await menuLabels(page);
      expect(labels).not.toContain("Delete");
      expect(labels.length).toBeGreaterThan(0);
    });
  },
);

test.describe(
  "ROM more-actions menu (admin)",
  { tag: "@page:gameDetails" },
  () => {
    test.use({ storageState: STORAGE_STATE.admin });

    test("still gets every action", async ({ page }) => {
      await seedUiState(page, "dark");
      await gotoFirstRom(page);
      const panel = await openMoreMenu(page);

      // Polled: items appear as grants resolve, so a single read can catch the
      // menu before they do.
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
  },
);
