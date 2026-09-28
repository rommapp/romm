import type { DetailedRom, SimpleRom } from "@/stores/roms";

export function makeRom(overrides: Partial<SimpleRom>): SimpleRom {
  return {
    id: 1,
    fs_name: "Game",
    files: [],
    ...overrides,
  } as SimpleRom;
}

export function makeDetailedRom(overrides: Partial<DetailedRom>): DetailedRom {
  return {
    id: 1,
    fs_name: "Game",
    files: [],
    ...overrides,
  } as DetailedRom;
}
