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
    ...makeRom(overrides),
    user_saves: [],
    user_states: [],
    all_user_saves: [],
    all_user_states: [],
    user_screenshots: [],
    all_user_screenshots: [],
    all_user_notes: [],
    ...overrides,
  } as DetailedRom;
}
