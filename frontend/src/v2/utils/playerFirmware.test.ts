import { describe, expect, it } from "vitest";
import { resolveInitialFirmware, selectableFirmware } from "./playerFirmware";

// Only these three fields are read; minimal stubs stand in for FirmwareSchema.
const fw = (id: number, file_name: string, missing_from_fs = false) => ({
  id,
  file_name,
  missing_from_fs,
});

describe("selectableFirmware", () => {
  it("drops entries whose file is gone from disk", () => {
    const options = [fw(1, "a.bin"), fw(2, "b.bin", true), fw(3, "c.bin")];
    expect(selectableFirmware(options).map((f) => f.id)).toEqual([1, 3]);
  });

  it("returns nothing when every entry is missing", () => {
    expect(selectableFirmware([fw(1, "a.bin", true)])).toEqual([]);
  });
});

describe("resolveInitialFirmware", () => {
  it("prefers the id the user last picked for the platform", () => {
    const options = [fw(1, "a.bin"), fw(2, "b.bin")];
    expect(
      resolveInitialFirmware({
        options,
        storedBiosId: "2",
        configBiosFile: "a.bin",
      })?.id,
    ).toBe(2);
  });

  it("falls back to the core config's bios_file", () => {
    const options = [fw(1, "a.bin"), fw(2, "b.bin")];
    expect(
      resolveInitialFirmware({
        options,
        storedBiosId: null,
        configBiosFile: "b.bin",
      })?.id,
    ).toBe(2);
  });

  it("auto-selects when the platform has exactly one usable entry", () => {
    expect(
      resolveInitialFirmware({
        options: [fw(7, "only.bin")],
        storedBiosId: null,
        configBiosFile: undefined,
      })?.id,
    ).toBe(7);
  });

  // Issue #4075: a single, stale entry used to be auto-selected, and the game
  // then failed to boot with nothing pointing at the BIOS.
  it("never auto-selects the sole entry when its file is missing", () => {
    expect(
      resolveInitialFirmware({
        options: [fw(7, "gone.bin", true)],
        storedBiosId: null,
        configBiosFile: undefined,
      }),
    ).toBeNull();
  });

  it("ignores a stored id that now points at missing firmware", () => {
    const options = [fw(1, "gone.bin", true), fw(2, "present.bin")];
    // Two usable entries would be ambiguous, so the fallback stays null rather
    // than guessing; what matters is the missing one is not picked.
    expect(
      resolveInitialFirmware({
        options,
        storedBiosId: "1",
        configBiosFile: undefined,
      })?.id,
    ).toBe(2);
  });

  it("ignores a config bios_file that now points at missing firmware", () => {
    const options = [fw(1, "gone.bin", true), fw(2, "present.bin")];
    expect(
      resolveInitialFirmware({
        options,
        storedBiosId: null,
        configBiosFile: "gone.bin",
      })?.id,
    ).toBe(2);
  });

  it("selects nothing when the platform has no firmware at all", () => {
    expect(
      resolveInitialFirmware({
        options: [],
        storedBiosId: null,
        configBiosFile: undefined,
      }),
    ).toBeNull();
  });

  it("selects nothing when several usable entries make the choice ambiguous", () => {
    expect(
      resolveInitialFirmware({
        options: [fw(1, "a.bin"), fw(2, "b.bin")],
        storedBiosId: null,
        configBiosFile: undefined,
      }),
    ).toBeNull();
  });
});
