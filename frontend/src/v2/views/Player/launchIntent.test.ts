import { describe, expect, it } from "vitest";
import { existingSlot } from "@/v2/utils/saveSlots";
import { isLaunchIntent, type LaunchIntent } from "./launchIntent";

const INTENT: LaunchIntent = {
  saveId: 3,
  stateId: null,
  firmwareId: 12,
  slot: existingSlot("slot-2"),
  customSlot: "",
};

describe("isLaunchIntent", () => {
  it("accepts what the view stores", () => {
    expect(isLaunchIntent(INTENT)).toBe(true);
  });

  it("accepts a cleared selection", () => {
    expect(
      isLaunchIntent({
        saveId: null,
        stateId: null,
        firmwareId: null,
        slot: { kind: "new" },
        customSlot: "my slot",
      }),
    ).toBe(true);
  });

  it.each([
    ["nothing", null],
    ["another shape", { core: "snes9x" }],
    ["a string id", { ...INTENT, saveId: "3" }],
    ["a bare slot name", { ...INTENT, slot: "slot-2" }],
    ["a missing slot name", { ...INTENT, customSlot: undefined }],
  ])("rejects %s", (_label, value) => {
    expect(isLaunchIntent(value)).toBe(false);
  });
});
