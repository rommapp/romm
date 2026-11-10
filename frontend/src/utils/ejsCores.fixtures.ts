import type { EJSCoresMaps } from "@/utils";

export function ejsCoresFixture(
  overrides: Partial<EJSCoresMaps> = {},
): EJSCoresMaps {
  return {
    EJS_CORES: {
      psx: ["pcsx_rearmed", "mednafen_psx_hw"],
      snes: ["snes9x"],
      dos: ["dosbox_pure"],
    },
    EJS_NIGHTLY_CORES: {
      snes: ["snes9x", "bsnes"],
      "3ds": ["azahar"],
    },
    ...overrides,
  };
}
