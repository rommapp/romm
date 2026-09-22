import type {
  DetailedRomSchema,
  RomMetadataSchema,
  RomUserSchema,
  SaveSchema,
  ScreenshotSchema,
  StateSchema,
  UserSaveSchema,
  UserSchema,
  UserStateSchema,
} from "@/__generated__";

export const STORY_NOW = new Date("2026-05-25T20:00:00Z").getTime();
const HOUR = 3600 * 1000;

const STORY_ASSET_AT = "2026-05-13T22:08:00Z";

/** Full `ScreenshotSchema` for state/save story rows (no type assertion). */
export function storyStateScreenshot(
  downloadPath: string,
  id = 1,
): ScreenshotSchema {
  return {
    id,
    rom_id: 1,
    user_id: 1,
    file_name: `state_shot_${id}.png`,
    file_name_no_tags: `state_shot_${id}`,
    file_name_no_ext: `state_shot_${id}`,
    file_extension: "png",
    file_path: "/states/shots",
    file_size_bytes: 4096,
    full_path: `/states/shots/state_shot_${id}.png`,
    download_path: downloadPath,
    missing_from_fs: false,
    created_at: STORY_ASSET_AT,
    updated_at: STORY_ASSET_AT,
  };
}

export function saveScreenshot(hue: number): ScreenshotSchema {
  const svg = `<svg xmlns='http://www.w3.org/2000/svg' width='64' height='36'><rect width='64' height='36' fill='hsl(${hue} 60% 40%)'/><rect x='8' y='8' width='48' height='20' fill='hsl(${hue} 70% 65%)'/></svg>`;
  return storyStateScreenshot(
    `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`,
    1000 + hue,
  );
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

const STATE_DEFAULTS: StateSchema = {
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
  updated_at: STORY_ASSET_AT,
  emulator: "snes9x",
  screenshot: storyStateScreenshot(
    "https://placehold.co/640x360/2d2147/ffffff?text=Save+State",
  ),
};

export function makeState(overrides: Partial<StateSchema> = {}): StateSchema {
  return { ...STATE_DEFAULTS, ...overrides };
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
        ? storyStateScreenshot(
            `https://placehold.co/640x360/${shot.color}/ffffff?text=${shot.label}`,
            i + 1,
          )
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

const STORY_ROM_METADATUM: RomMetadataSchema = {
  rom_id: 1,
  genres: [],
  franchises: [],
  collections: [],
  companies: [],
  publishers: [],
  developers: [],
  game_modes: [],
  age_ratings: [],
  player_count: "1",
  first_release_date: Date.UTC(1995, 2, 11),
  average_rating: null,
};

const STORY_ROM_USER: RomUserSchema = {
  id: 1,
  user_id: 1,
  rom_id: 1,
  created_at: "2026-01-02T00:00:00Z",
  updated_at: "2026-01-02T00:00:00Z",
  last_played: null,
  is_main_sibling: true,
  backlogged: false,
  now_playing: false,
  hidden: false,
  rating: 0,
  difficulty: 0,
  completion: 0,
  status: null,
};

/** Complete defaults so new required `DetailedRomSchema` fields fail typecheck here. */
const STORY_DETAILED_ROM_DEFAULTS: DetailedRomSchema = {
  id: 1,
  igdb_id: null,
  sgdb_id: null,
  moby_id: null,
  ss_id: null,
  ra_id: null,
  launchbox_id: null,
  hasheous_id: null,
  tgdb_id: null,
  flashpoint_id: null,
  hltb_id: null,
  demozoo_id: null,
  pouet_id: null,
  csdb_id: null,
  steam_id: null,
  gamelist_id: null,
  libretro_id: null,
  platform_id: 3,
  platform_slug: "snes",
  platform_fs_slug: "snes",
  platform_custom_name: null,
  platform_display_name: "Super Nintendo",
  fs_name: "Chrono Trigger.sfc",
  fs_name_no_tags: "Chrono Trigger",
  fs_name_no_ext: "Chrono Trigger",
  fs_extension: "sfc",
  fs_path: "snes/Chrono Trigger.sfc",
  fs_size_bytes: 4_194_304,
  name: "Chrono Trigger",
  name_sort_key: "chrono trigger",
  slug: "chrono-trigger",
  summary: null,
  alternative_names: [],
  youtube_video_id: null,
  metadatum: STORY_ROM_METADATUM,
  igdb_metadata: null,
  moby_metadata: null,
  ss_metadata: null,
  launchbox_metadata: null,
  hasheous_metadata: null,
  flashpoint_metadata: null,
  hltb_metadata: null,
  demozoo_metadata: null,
  pouet_metadata: null,
  csdb_metadata: null,
  steam_metadata: null,
  gamelist_metadata: null,
  manual_metadata: null,
  path_cover_small: null,
  path_cover_large: null,
  url_cover: null,
  has_manual: false,
  has_soundtrack: false,
  path_manual: null,
  url_manual: null,
  path_video: null,
  is_unidentified: false,
  is_identified: true,
  revision: null,
  regions: ["USA"],
  languages: ["en"],
  tags: [],
  crc_hash: null,
  md5_hash: null,
  sha1_hash: null,
  ra_hash: null,
  title_id: null,
  save_target: null,
  save_target_layout: null,
  has_simple_single_file: true,
  has_nested_single_file: false,
  has_multiple_files: false,
  full_path: "/romm/library/snes/Chrono Trigger.sfc",
  created_at: "2026-01-02T00:00:00Z",
  updated_at: "2026-01-02T00:00:00Z",
  missing_from_fs: false,
  is_physical: false,
  has_file_on_disk: true,
  upc: null,
  has_notes: false,
  rom_user: STORY_ROM_USER,
  merged_screenshots: [],
  merged_ra_metadata: null,
  files: [],
  sibling_roms: [],
  user_saves: [],
  user_states: [],
  all_user_saves: [],
  all_user_states: [],
  user_screenshots: [],
  all_user_screenshots: [],
  user_collections: [],
  all_user_notes: [],
};

export function storyDetailedRom(
  overrides: Partial<DetailedRomSchema> = {},
): DetailedRomSchema {
  return {
    ...STORY_DETAILED_ROM_DEFAULTS,
    all_user_saves: mixedCommunitySaves(),
    all_user_states: mixedCommunityStates(),
    ...overrides,
  };
}

const STORY_AUTH_USER: UserSchema = {
  id: 1,
  username: "player",
  email: null,
  enabled: true,
  role: "admin",
  oauth_scopes: [],
  avatar_path: "",
  last_login: null,
  last_active: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

export function storyAuthUser(overrides: Partial<UserSchema> = {}): UserSchema {
  return { ...STORY_AUTH_USER, ...overrides };
}
