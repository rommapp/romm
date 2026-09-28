import type { Locator, Page } from "@playwright/test";
import { gotoFirstRom, seedUiState, STORAGE_STATE } from "./fixtures/auth";
import { expect, test } from "./fixtures/test";

// The Media and Files tabs write to the ROM (manuals, soundtracks, shared
// screenshots, ROM files) and every one of those endpoints gates on ROMS_WRITE.
// A read-only user must not be offered upload/delete there -- same 403-to-logout
// trap as the ⋯ menu.
//
// The per-user "My screenshots" section is the deliberate exception: it writes
// user assets, which every authenticated user may do.
//
// NOTE: MediaTab keeps every subtab panel mounted (v-show, not v-if) so the
// heavy async panels don't re-mount on each switch. Assertions must therefore
// scope to the VISIBLE panel -- a document-wide locator would also match the
// hidden panels and pass or fail for the wrong reason.
//
// Sessions come from auth.setup.ts; see login.spec.ts for the form itself.

async function openTab(page: Page, tab: string) {
  await page.getByRole("tab", { name: tab }).click();
}

// Media subtabs are a sidebar list of role=tab buttons, distinct from the
// top-level RTabNav tabs.
async function openSubtab(page: Page, subtab: string) {
  await page.locator(".r-v2-subtab-nav__btn", { hasText: subtab }).click();
}

/** The one Media panel currently on screen. */
function visiblePanel(page: Page): Locator {
  return page.locator(".r-v2-media__panel:visible");
}

// Both panels whose upload path is ROM-scoped, so both must be inert.
const ROM_SCOPED_SUBTABS = [
  ["Manual", "No manual yet"],
  ["Soundtrack", "No soundtrack yet"],
] as const;

test.describe("Media tab write affordances (read-only user)", () => {
  test.use({ storageState: STORAGE_STATE.viewer });

  for (const [subtab, emptyText] of ROM_SCOPED_SUBTABS) {
    test(`${subtab}: gets the empty state, not a dropzone`, async ({
      page,
    }) => {
      await seedUiState(page, "dark");
      await gotoFirstRom(page);
      await openTab(page, "Media");
      await openSubtab(page, subtab);

      const panel = visiblePanel(page);
      // The plain REmptyState replaces the dropzone: same message, no CTA,
      // no drag-and-drop hint, no Upload button.
      await expect(panel.getByText(emptyText)).toBeVisible();
      await expect(panel.locator(".r-dropzone__cta")).toHaveCount(0);
      await expect(
        panel.getByText("Drag and drop, or click to browse"),
      ).toHaveCount(0);
      await expect(
        panel.getByRole("button", { name: "Upload", exact: true }),
      ).toHaveCount(0);
    });
  }

  test("Screenshots: the shared ROM section is hidden but the per-user one stays writable", async ({
    page,
  }) => {
    await seedUiState(page, "dark");
    await gotoFirstRom(page);
    await openTab(page, "Media");
    await openSubtab(page, "Screenshots");

    const panel = visiblePanel(page);
    // Shared section writes to the ROM: gone for a read-only user with nothing
    // to show.
    await expect(panel.getByText("ROM screenshots")).toHaveCount(0);
    // Per-user section writes user assets: must survive, dropzone included.
    // Hiding this would be the regression in the opposite direction.
    await expect(panel.getByText("My screenshots")).toBeVisible();
    await expect(panel.locator(".r-dropzone__cta")).not.toHaveCount(0);
  });
});

test.describe("Media tab write affordances (admin)", () => {
  test.use({ storageState: STORAGE_STATE.admin });

  for (const [subtab] of ROM_SCOPED_SUBTABS) {
    test(`${subtab}: still gets the dropzone`, async ({ page }) => {
      await seedUiState(page, "dark");
      await gotoFirstRom(page);
      await openTab(page, "Media");
      await openSubtab(page, subtab);

      const panel = visiblePanel(page);
      // Empty ROM => CTA dropzone; populated ROM => Upload button. Either is a
      // write affordance, and a read-only user gets neither. `.or()` keeps this
      // auto-waiting: a bare `count()` reads 0 before the async panel mounts.
      const writeAffordance = panel
        .locator(".r-dropzone__cta")
        .or(panel.getByRole("button", { name: "Upload", exact: true }));
      await expect(writeAffordance.first()).toBeVisible();
    });
  }

  test("Screenshots: sees the shared ROM section", async ({ page }) => {
    await seedUiState(page, "dark");
    await gotoFirstRom(page);
    await openTab(page, "Media");
    await openSubtab(page, "Screenshots");

    await expect(visiblePanel(page).getByText("ROM screenshots")).toBeVisible();
  });
});

// "All files" has no destination of its own, so it offers "Upload to folder";
// a folder subtab offers Upload straight into that folder.
function uploadButton(page: Page): Locator {
  return page.getByRole("button", { name: "Upload", exact: true });
}

function uploadToFolderButton(page: Page): Locator {
  return page.getByRole("button", { name: "Upload to folder", exact: true });
}

test.describe("Files tab write affordances", () => {
  test.describe("read-only user", () => {
    test.use({ storageState: STORAGE_STATE.viewer });

    test("gets no upload button", async ({ page }) => {
      await seedUiState(page, "dark");
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
      await seedUiState(page, "dark");
      await gotoFirstRom(page);
      await openTab(page, "Files");

      await expect(uploadToFolderButton(page)).toBeVisible();
      await expect(uploadButton(page)).toHaveCount(0);
    });

    test("gets Upload from a folder subtab", async ({ page }) => {
      await seedUiState(page, "dark");
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
