import type {
  SaveSchema,
  ScreenshotSchema,
  StateSchema,
  UserSaveSchema,
  UserStateSchema,
} from "@/__generated__";

export const STORY_NOW = new Date("2026-05-25T20:00:00Z").getTime();
const HOUR = 3600 * 1000;

export function saveScreenshot(hue: number): ScreenshotSchema {
  const svg = `<svg xmlns='http://www.w3.org/2000/svg' width='64' height='36'><rect width='64' height='36' fill='hsl(${hue} 60% 40%)'/><rect x='8' y='8' width='48' height='20' fill='hsl(${hue} 70% 65%)'/></svg>`;
  return {
    download_path: `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`,
  } as ScreenshotSchema;
}

export function makeSave(
  id: number,
  slot: string | null,
  hoursAgo: number,
  overrides: Partial<SaveSchema> = {},
): SaveSchema {
  const at = new Date(STORY_NOW - hoursAgo * HOUR).toISOString();
  const stem = slot
    ? `chrono_trigger [${at.slice(0, 19).replace("T", "_").replace(/:/g, "-")}]`
    : `chrono_trigger_backup_${id}`;
  return {
    id,
    rom_id: 1,
    user_id: 1,
    file_name: `${stem}.srm`,
    file_name_no_tags: "chrono_trigger.srm",
    file_name_no_ext: stem,
    file_extension: "srm",
    file_path: "/saves/snes",
    file_size_bytes: 8 * 1024,
    full_path: `/saves/snes/${stem}.srm`,
    download_path: `/api/saves/${id}/content`,
    missing_from_fs: false,
    created_at: at,
    updated_at: at,
    emulator: "snes9x",
    slot,
    screenshot: null,
    ...overrides,
  } as SaveSchema;
}

export function makeSaveSlot(
  slot: string,
  count: number,
  hoursAgo: number,
  firstId: number,
): SaveSchema[] {
  return Array.from({ length: count }).map((_, i) =>
    makeSave(firstId + i, slot, hoursAgo + i * 26, {
      screenshot: saveScreenshot((i * 47 + slot.length * 31) % 360),
    }),
  );
}

export function saveSlotLibrary(): SaveSchema[] {
  return [
    ...makeSaveSlot("autosave", 4, 1, 1),
    ...makeSaveSlot("main_quest", 6, 30, 5),
    ...makeSaveSlot("speedrun", 1, 200, 11),
    makeSave(12, null, 500),
    makeSave(13, null, 900, { emulator: null }),
  ];
}

export function makeState(overrides: Partial<StateSchema> = {}): StateSchema {
  const base = {
    id: 1,
    rom_id: 1,
    user_id: 1,
    file_name: "state_1.state",
    file_name_no_tags: "state_1.state",
    file_name_no_ext: "state_1",
    file_extension: "state",
    file_path: "/states/snes",
    file_size_bytes: 524288,
    full_path: "/states/snes/state_1.state",
    download_path: "/api/states/1/content",
    missing_from_fs: false,
    created_at: "2026-04-02T09:00:00Z",
    updated_at: "2026-05-13T22:08:00Z",
    emulator: "snes9x",
    screenshot: {
      download_path:
        "https://placehold.co/640x360/2d2147/ffffff?text=Save+State",
    } as StateSchema["screenshot"],
  };
  return { ...base, ...overrides } as StateSchema;
}

const stateShotPalette: { color: string; label: string }[] = [
  { color: "2d2147", label: "Overworld" },
  { color: "1a3d2e", label: "Forest" },
  { color: "4a1a1a", label: "Boss+Fight" },
  { color: "0a3a5a", label: "Cave" },
  { color: "5a3a0a", label: "Desert" },
  { color: "3a0a4a", label: "Castle" },
  { color: "0a5a3a", label: "Lake" },
  { color: "5a0a3a", label: "Volcano" },
  { color: "1a1a5a", label: "Sky" },
  { color: "5a5a0a", label: "Tower" },
];

export function manyStates(n: number, withScreenshots = true): StateSchema[] {
  const deltas = [
    2 * 3600,
    5 * 3600,
    24 * 3600,
    2 * 86400,
    4 * 86400,
    7 * 86400,
    14 * 86400,
    30 * 86400,
    60 * 86400,
    180 * 86400,
  ];
  return Array.from({ length: n }).map((_, i) => {
    const shot = stateShotPalette[i % stateShotPalette.length];
    return makeState({
      id: i + 1,
      file_name: `${shot.label.replace("+", " ").toLowerCase()}_${i + 1}.state`,
      file_size_bytes: 256 * 1024 + i * 73 * 1024,
      updated_at: new Date(
        STORY_NOW - deltas[i % deltas.length] * 1000,
      ).toISOString(),
      screenshot: withScreenshots
        ? ({
            ...(makeState().screenshot as NonNullable<
              StateSchema["screenshot"]
            >),
            download_path: `https://placehold.co/640x360/${shot.color}/ffffff?text=${shot.label}`,
          } as StateSchema["screenshot"])
        : null,
      emulator: i % 3 === 0 ? "snes9x" : i % 3 === 1 ? "mesen" : null,
    });
  });
}

/** Browser-player states share a prefix; timestamps at the end get ellipsised. */
export function identicalPrefixStates(count: number): StateSchema[] {
  const prefix =
    "emulatorjs_chrono_trigger_usa_rev_a_super_nintendo_2026-05-25";
  return Array.from({ length: count }).map((_, i) => {
    const tail = new Date(STORY_NOW - (i + 1) * HOUR).toISOString();
    return makeState({
      id: i + 1,
      file_name: `${prefix}_${tail.replace(/[:.]/g, "-")}.state`,
      updated_at: tail,
      emulator: i % 2 === 0 ? "snes9x" : "mesen",
    });
  });
}

export function toUserSave(
  save: SaveSchema,
  username: string,
  overrides: Partial<UserSaveSchema> = {},
): UserSaveSchema {
  return {
    ...save,
    username,
    is_public: true,
    user_avatar_path: undefined,
    user_updated_at: save.updated_at,
    ...overrides,
  } as UserSaveSchema;
}

export function toUserState(
  state: StateSchema,
  username: string,
  overrides: Partial<UserStateSchema> = {},
): UserStateSchema {
  return {
    ...state,
    username,
    is_public: true,
    user_avatar_path: undefined,
    user_updated_at: state.updated_at,
    ...overrides,
  } as UserStateSchema;
}

/** Mine (user 1) plus community saves for Save data / showOwner stories. */
export function mixedCommunitySaves(): UserSaveSchema[] {
  const mine = saveSlotLibrary().map((s) =>
    toUserSave(s, "player", { user_id: 1, is_public: s.id % 3 === 0 }),
  );
  const theirs = makeSaveSlot("shared_route", 2, 40, 100).map((s, i) =>
    toUserSave({ ...s, id: 100 + i, user_id: 2 }, "speedrunner42", {
      is_public: true,
    }),
  );
  return [...mine, ...theirs];
}

export function mixedCommunityStates(): UserStateSchema[] {
  const mine = manyStates(4).map((s) =>
    toUserState(s, "player", { user_id: 1, is_public: true }),
  );
  const theirs = manyStates(3).map((s, i) =>
    toUserState(
      { ...s, id: 50 + i, user_id: 3, emulator: "mesen" },
      "archivist",
      { is_public: true },
    ),
  );
  return [...mine, ...theirs];
}
