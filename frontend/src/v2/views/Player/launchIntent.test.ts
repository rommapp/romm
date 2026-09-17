import { describe, expect, it } from "vitest";
import type { FirmwareSchema, SaveSchema, StateSchema } from "@/__generated__";
import { existingSlot } from "@/v2/utils/saveSlots";
import {
  isLaunchIntent,
  launchIntentFor,
  resolveLaunchIntent,
  type LaunchIntent,
  type LaunchOptions,
  type LaunchSelection,
} from "./launchIntent";

function makeSave(overrides: Partial<SaveSchema> = {}): SaveSchema {
  return { id: 3, slot: "slot-2", ...overrides } as SaveSchema;
}

function makeState(overrides: Partial<StateSchema> = {}): StateSchema {
  return { id: 5, emulator: "snes9x", ...overrides } as StateSchema;
}

function makeFirmware(overrides: Partial<FirmwareSchema> = {}): FirmwareSchema {
  return { id: 12, file_name: "bios.bin", ...overrides } as FirmwareSchema;
}

const save = makeSave();
const state = makeState();
const firmware = makeFirmware();

const OPTIONS: LaunchOptions = {
  saves: [save],
  states: [state],
  firmware: [firmware],
};

const SELECTION: LaunchSelection = {
  resume: { save, state: null },
  firmware,
  slot: existingSlot("slot-2"),
  customSlot: "",
};

const INTENT: LaunchIntent = {
  saveId: 3,
  stateId: null,
  firmwareId: 12,
  slot: existingSlot("slot-2"),
  customSlot: "",
};

const EMPTY: LaunchSelection = {
  resume: { save: null, state: null },
  firmware: null,
  slot: { kind: "new" },
  customSlot: "my slot",
};

describe("launchIntentFor", () => {
  it("names the selection by id", () => {
    expect(launchIntentFor(SELECTION)).toEqual(INTENT);
  });

  it("names a state pick over a save", () => {
    expect(
      launchIntentFor({ ...SELECTION, resume: { save: null, state } }),
    ).toEqual({ ...INTENT, saveId: null, stateId: 5 });
  });

  it("carries a cleared selection", () => {
    expect(launchIntentFor(EMPTY)).toEqual({
      saveId: null,
      stateId: null,
      firmwareId: null,
      slot: { kind: "new" },
      customSlot: "my slot",
    });
  });
});

describe("resolveLaunchIntent", () => {
  it("round-trips a selection through its intent", () => {
    expect(resolveLaunchIntent(launchIntentFor(SELECTION), OPTIONS)).toEqual(
      SELECTION,
    );
  });

  it("round-trips a cleared selection", () => {
    expect(resolveLaunchIntent(launchIntentFor(EMPTY), OPTIONS)).toEqual(EMPTY);
  });

  // A save deleted from another tab, or a state the reloaded core cannot read,
  // is simply not offered any more.
  it.each([
    ["save", { ...INTENT, saveId: 99 }, "save"],
    ["state", { ...INTENT, saveId: null, stateId: 99 }, "state"],
  ])("drops a %s that is no longer offered", (_label, intent, key) => {
    const resolved = resolveLaunchIntent(intent as LaunchIntent, OPTIONS);

    expect(resolved.resume[key as "save" | "state"]).toBeNull();
  });

  it("drops firmware that is no longer offered", () => {
    expect(
      resolveLaunchIntent({ ...INTENT, firmwareId: 99 }, OPTIONS).firmware,
    ).toBeNull();
  });

  it("keeps the slot the session writes to", () => {
    const resolved = resolveLaunchIntent(
      { ...INTENT, slot: { kind: "new" }, customSlot: "speedrun" },
      OPTIONS,
    );

    expect(resolved.slot).toEqual({ kind: "new" });
    expect(resolved.customSlot).toBe("speedrun");
  });
});

describe("isLaunchIntent", () => {
  it("accepts what the view stores", () => {
    expect(isLaunchIntent(INTENT)).toBe(true);
  });

  it("accepts a cleared selection", () => {
    expect(isLaunchIntent(launchIntentFor(EMPTY))).toBe(true);
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
