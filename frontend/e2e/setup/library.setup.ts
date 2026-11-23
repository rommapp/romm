import { writeFileSync } from "node:fs";
import { STORAGE_STATE } from "../support/auth";
import { clickThroughToFirstRom, type Library } from "../support/navigation";
import { LIBRARY_FILE } from "../support/output";
import { expect, test as setup } from "../support/test";

// Finds the first game once, so specs open it by URL instead of each clicking
// through the platforms to reach it.
setup.use({ storageState: STORAGE_STATE.admin });

setup("find the first game", async ({ page }) => {
  await clickThroughToFirstRom(page);
  const library: Library = { firstRom: new URL(page.url()).pathname };
  expect(library.firstRom).toMatch(/^\/rom\/\d+$/);
  writeFileSync(LIBRARY_FILE, JSON.stringify(library));
});
