import { gotoHydrated, seedUiState, STORAGE_STATE } from "./fixtures/auth";
import { expect, test } from "./fixtures/test";

// Tagged @devices, so it runs on every device project (src/v2/devices.ts).
test.use({ storageState: STORAGE_STATE.viewer });

test(
  "a handheld with built-in controls starts in gamepad modality",
  { tag: "@devices" },
  async ({ page, gamepad }) => {
    test.skip(!gamepad, "Only devices with built-in game controls.");
    await seedUiState(page, "dark");
    await gotoHydrated(page, "/");

    // Focus rings, autofocus and hover suppression all key off this.
    await expect(page.locator("html")).toHaveAttribute("data-input", "pad");
  },
);
