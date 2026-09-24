import type { SimpleRom } from "@/stores/roms";

export function makeRom(overrides: Partial<SimpleRom>): SimpleRom {
  return {
    id: 1,
    fs_name: "Game",
    files: [],
    ...overrides,
  } as SimpleRom;
}
