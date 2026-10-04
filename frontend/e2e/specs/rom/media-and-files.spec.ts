import type { Locator, Page } from "@playwright/test";
import { STORAGE_STATE } from "../../support/auth";
import { gotoFirstRom } from "../../support/navigation";
import { expect, test } from "../../support/test";

// A viewer gets no ROMS_WRITE upload or delete on the Media and Files tabs.
// "My screenshots" writes the user's own assets, so it stays.

async function openTab(page: Page, tab: string) {
  await page.getByRole("tab", { name: tab }).click();
}

/** Open a Media subtab of the first game and return its panel; the others stay
 *  mounted (v-show). Subtabs are a sidebar list, distinct from RTabNav's tabs. */
async function openMediaSubtab(page: Page, subtab: string): Promise<Locator> {
  await gotoFirstRom(page);
  await openTab(page, "Media");
  await page.locator(".r-v2-subtab-nav__btn", { hasText: subtab }).click();
  return page.locator(".r-v2-media__panel:visible");
}

function uploadButton(scope: Page | Locator): Locator {
  return scope.getByRole("button", { name: "Upload", exact: true });
}

function uploadToFolderButton(scope: Page | Locator): Locator {
  return scope.getByRole("button", { name: "Upload to folder", exact: true });
}

// Both panels whose upload path is ROM-scoped, so both must be inert.
const ROM_SCOPED_SUBTABS = [
  ["Manual", "No manual yet"],
  ["Soundtrack", "No soundtrack yet"],
] as const;

test.describe(
  "Media tab write affordances (read-only user)",
  { tag: "@page:rom" },
  () => {
    test.use({ storageState: STORAGE_STATE.viewer });

    for (const [subtab, emptyText] of ROM_SCOPED_SUBTABS) {
      test(`${subtab}: gets the empty state, not a dropzone`, async ({
        page,
      }) => {
        const panel = await openMediaSubtab(page, subtab);
        // The plain REmptyState replaces the dropzone: same message, no CTA,
        // no drag-and-drop hint, no Upload button.
        await expect(panel.getByText(emptyText)).toBeVisible();
        await expect(panel.locator(".r-dropzone__cta")).toHaveCount(0);
        await expect(
          panel.getByText("Drag and drop, or click to browse"),
        ).toHaveCount(0);
        await expect(uploadButton(panel)).toHaveCount(0);
      });
    }

    test("Screenshots: the shared ROM section is hidden but the per-user one stays writable", async ({
      page,
    }) => {
      const panel = await openMediaSubtab(page, "Screenshots");
      // Shared section writes to the ROM: gone for a read-only user with nothing
      // to show.
      await expect(panel.getByText("ROM screenshots")).toHaveCount(0);
      // Per-user section writes user assets: must survive, dropzone included.
      // Hiding this would be the regression in the opposite direction.
      await expect(panel.getByText("My screenshots")).toBeVisible();
      await expect(panel.locator(".r-dropzone__cta")).not.toHaveCount(0);
    });
  },
);

test.describe(
  "Media tab write affordances (admin)",
  { tag: "@page:rom" },
  () => {
    test.use({ storageState: STORAGE_STATE.admin });

    for (const [subtab] of ROM_SCOPED_SUBTABS) {
      test(`${subtab}: still gets the dropzone`, async ({ page }) => {
        const panel = await openMediaSubtab(page, subtab);
        // Empty ROM shows the dropzone, a populated one the Upload button.
        // `.or()` auto-waits; `count()` reads 0 before the async panel mounts.
        const writeAffordance = panel
          .locator(".r-dropzone__cta")
          .or(uploadButton(panel));
        await expect(writeAffordance.first()).toBeVisible();
      });
    }

    test("Screenshots: sees the shared ROM section", async ({ page }) => {
      const panel = await openMediaSubtab(page, "Screenshots");

      await expect(panel.getByText("ROM screenshots")).toBeVisible();
    });
  },
);

// "All files" has no destination of its own, so it offers "Upload to folder";
// a folder subtab offers Upload straight into that folder.
test.describe("Files tab write affordances", { tag: "@page:rom" }, () => {
  test.describe("read-only user", () => {
    test.use({ storageState: STORAGE_STATE.viewer });

    test("gets no upload button", async ({ page }) => {
      await gotoFirstRom(page);
      await openTab(page, "Files");

      await expect(page.locator(".r-v2-subtab-nav__btn").first()).toBeVisible();
      await expect(uploadButton(page)).toHaveCount(0);
      await expect(uploadToFolderButton(page)).toHaveCount(0);
    });
  });

  test.describe("admin", () => {
    test.use({ storageState: STORAGE_STATE.admin });

    test("gets Upload to folder from All files", async ({ page }) => {
      await gotoFirstRom(page);
      await openTab(page, "Files");

      await expect(uploadToFolderButton(page)).toBeVisible();
      await expect(uploadButton(page)).toHaveCount(0);
    });

    test("gets Upload from a folder subtab", async ({ page }) => {
      await gotoFirstRom(page);
      await openTab(page, "Files");
      await page
        .locator(".r-v2-subtab-nav__btn:not(.r-v2-subtab-nav__btn--active)")
        .first()
        .click();

      await expect(uploadButton(page)).toBeVisible();
      await expect(uploadToFolderButton(page)).toHaveCount(0);
    });
  });
});
