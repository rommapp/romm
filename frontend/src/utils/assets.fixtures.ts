import type { SaveSchema, StateSchema } from "@/__generated__";

const WRITTEN_AT = "2026-09-16T12:00:00Z";

export function saveFixture(overrides: Partial<SaveSchema> = {}): SaveSchema {
  return {
    id: 1,
    rom_id: 1,
    user_id: 1,
    file_name: "game.srm",
    file_name_no_tags: "game",
    file_name_no_ext: "game",
    file_extension: "srm",
    file_path: "saves",
    file_size_bytes: 1024,
    full_path: "saves/game.srm",
    download_path: "/api/saves/1/content/game.srm",
    missing_from_fs: false,
    created_at: WRITTEN_AT,
    updated_at: WRITTEN_AT,
    emulator: null,
    slot: null,
    screenshot: null,
    ...overrides,
  };
}

export function stateFixture(
  overrides: Partial<StateSchema> = {},
): StateSchema {
  return {
    id: 1,
    rom_id: 1,
    user_id: 1,
    file_name: "game.state",
    file_name_no_tags: "game",
    file_name_no_ext: "game",
    file_extension: "state",
    file_path: "states",
    file_size_bytes: 1024,
    full_path: "states/game.state",
    download_path: "/api/states/1/content/game.state",
    missing_from_fs: false,
    created_at: WRITTEN_AT,
    updated_at: WRITTEN_AT,
    emulator: null,
    screenshot: null,
    ...overrides,
  };
}
