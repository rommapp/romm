import { describe, expect, it } from "vitest";
import type { Config } from "@/stores/config";
import type { Heartbeat } from "@/stores/heartbeat";
import type { SimpleRom } from "@/stores/roms";
import {
  getDownloadPath,
  isJsDosBundle,
  isJsDosEmulationSupported,
} from "./index";

function makeRom(overrides: Partial<SimpleRom>): SimpleRom {
  return {
    id: 1,
    fs_name: "Game",
    files: [],
    ...overrides,
  } as SimpleRom;
}

describe("getDownloadPath", () => {
  it("uses fs_name for a flat single-file rom", () => {
    const rom = makeRom({
      id: 14,
      fs_name: "Maniac Mansion (1989).adf",
      has_nested_single_file: false,
      files: [
        { id: 19, file_name: "Maniac Mansion (1989).adf" },
      ] as SimpleRom["files"],
    });
    expect(getDownloadPath({ rom })).toBe(
      "/api/roms/14/content/Maniac Mansion (1989).adf",
    );
  });

  it("uses the file name for a nested single-file rom", () => {
    const rom = makeRom({
      id: 21,
      fs_name: "Art Of Fighting",
      has_nested_single_file: true,
      files: [{ id: 26, file_name: "aof.zip" }] as SimpleRom["files"],
    });
    expect(getDownloadPath({ rom })).toBe("/api/roms/21/content/aof.zip");
  });

  it("uses fs_name for an unselected multi-file rom", () => {
    const rom = makeRom({
      id: 24,
      fs_name: "B.A.T.",
      has_nested_single_file: false,
      files: [
        { id: 29, file_name: "B.A.T. Disk1.adf" },
        { id: 30, file_name: "B.A.T. Disk2.adf" },
      ] as SimpleRom["files"],
    });
    expect(getDownloadPath({ rom })).toBe("/api/roms/24/content/B.A.T.");
  });

  it("uses the selected file name (with extension) for a single file", () => {
    // Multi-file rom: fs_name is the folder name with no extension. The URL
    // path segment must carry the selected file's real name so the emulator
    // receives a file with the correct extension.
    const rom = makeRom({
      id: 24,
      fs_name: "B.A.T.",
      files: [
        { id: 29, file_name: "B.A.T. Disk1.adf" },
        { id: 30, file_name: "B.A.T. Disk2.adf" },
      ] as SimpleRom["files"],
    });
    expect(getDownloadPath({ rom, fileIDs: [29] })).toBe(
      "/api/roms/24/content/B.A.T.%20Disk1.adf?file_ids=29",
    );
  });

  it("falls back to fs_name when multiple files are selected (zip)", () => {
    const rom = makeRom({
      id: 24,
      fs_name: "B.A.T.",
      files: [
        { id: 29, file_name: "B.A.T. Disk1.adf" },
        { id: 30, file_name: "B.A.T. Disk2.adf" },
      ] as SimpleRom["files"],
    });
    expect(getDownloadPath({ rom, fileIDs: [29, 30] })).toBe(
      "/api/roms/24/content/B.A.T.?file_ids=29%2C30",
    );
  });

  it("falls back to fs_name when the selected file id is unknown", () => {
    const rom = makeRom({ id: 24, fs_name: "B.A.T." });
    expect(getDownloadPath({ rom, fileIDs: [999] })).toBe(
      "/api/roms/24/content/B.A.T.?file_ids=999",
    );
  });
});

function makeHeartbeat(
  emulation: Partial<Heartbeat["EMULATION"]> = {},
): Heartbeat {
  return {
    EMULATION: {
      DISABLE_EMULATOR_JS: false,
      DISABLE_RUFFLE_RS: false,
      DISABLE_JSDOS: false,
      ...emulation,
    },
  } as Heartbeat;
}

function makeConfig(versions: Record<string, string> = {}): Config {
  return { PLATFORMS_VERSIONS: versions } as Config;
}

describe("isJsDosEmulationSupported", () => {
  it("supports win3x and win9x", () => {
    expect(isJsDosEmulationSupported("win3x", makeHeartbeat())).toBe(true);
    expect(isJsDosEmulationSupported("win9x", makeHeartbeat())).toBe(true);
  });

  it("is case-insensitive on the slug", () => {
    expect(isJsDosEmulationSupported("WIN3X", makeHeartbeat())).toBe(true);
  });

  it("does not claim dos or other platforms", () => {
    expect(isJsDosEmulationSupported("dos", makeHeartbeat())).toBe(false);
    expect(isJsDosEmulationSupported("flash", makeHeartbeat())).toBe(false);
    expect(isJsDosEmulationSupported("snes", makeHeartbeat())).toBe(false);
  });

  it("respects the DISABLE_JSDOS admin toggle", () => {
    expect(
      isJsDosEmulationSupported(
        "win3x",
        makeHeartbeat({ DISABLE_JSDOS: true }),
      ),
    ).toBe(false);
  });

  it("honours a PLATFORMS_VERSIONS remap onto win3x", () => {
    expect(
      isJsDosEmulationSupported(
        "dos",
        makeHeartbeat(),
        makeConfig({ dos: "win3x" }),
      ),
    ).toBe(true);
  });
});

describe("isJsDosBundle", () => {
  const withExt = (fs_extension: string) => makeRom({ fs_extension });

  it("accepts a .jsdos bundle regardless of case", () => {
    expect(isJsDosBundle(withExt("jsdos"))).toBe(true);
    expect(isJsDosBundle(withExt("JSDOS"))).toBe(true);
  });

  // js-dos panics with "Broken bundle" on anything that is not its own format.
  it("rejects plain archives, bare executables and folders", () => {
    expect(isJsDosBundle(withExt("zip"))).toBe(false);
    expect(isJsDosBundle(withExt("exe"))).toBe(false);
    expect(isJsDosBundle(withExt(""))).toBe(false);
  });

  it("rejects a missing rom", () => {
    expect(isJsDosBundle(null)).toBe(false);
    expect(isJsDosBundle(undefined)).toBe(false);
  });
});
