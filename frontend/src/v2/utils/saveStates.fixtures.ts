import type {
  DetailedRomSchema,
  SaveSchema,
  ScreenshotSchema,
  StateSchema,
  UserSaveSchema,
  UserStateSchema,
} from "@/__generated__";
import { saveFixture, stateFixture } from "@/utils/assets.fixtures";
import { makeDetailedRom } from "@/utils/rom.fixtures";

// Relative to the real clock, since AssetTimestamp formats against Date.now().
const STORY_NOW = Date.now();
const HOUR = 3600 * 1000;

export function hoursAgo(hours: number): string {
  return new Date(STORY_NOW - hours * HOUR).toISOString();
}

const WRITTEN_AT = hoursAgo(12 * 24);

export const IDENTICAL_STATE_PREFIX =
  "emulatorjs_chrono_trigger_usa_rev_a_super_nintendo";

export function screenshotFixture(
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
    created_at: WRITTEN_AT,
    updated_at: WRITTEN_AT,
  };
}

// 16:9 SVG stand-in for the screenshot a browser-player save carries.
export function saveScreenshot(hue: number): ScreenshotSchema {
  const svg = `<svg xmlns='http://www.w3.org/2000/svg' width='64' height='36'><rect width='64' height='36' fill='hsl(${hue} 60% 40%)'/><rect x='8' y='8' width='48' height='20' fill='hsl(${hue} 70% 65%)'/></svg>`;
  return screenshotFixture(
    `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`,
    1000 + hue,
  );
}

// One version in `slot`, `age` hours old. Pass `slot: null` for an archive.
export function makeSave(
  id: number,
  slot: string | null,
  age: number,
  overrides: Partial<SaveSchema> = {},
): SaveSchema {
  const at = hoursAgo(age);
  // Slotted uploads carry the backend's datetime tag; archives keep their name.
  const stem = slot
    ? `chrono_trigger [${at.slice(0, 19).replace("T", "_").replace(/:/g, "-")}]`
    : `chrono_trigger_backup_${id}`;
  return saveFixture({
    id,
    file_name: `${stem}.srm`,
    file_name_no_tags: "chrono_trigger.srm",
    file_name_no_ext: stem,
    file_path: "/saves/snes",
    file_size_bytes: 8 * 1024,
    full_path: `/saves/snes/${stem}.srm`,
    download_path: `/api/saves/${id}/content`,
    created_at: at,
    updated_at: at,
    emulator: "snes9x",
    slot,
    ...overrides,
  });
}

// A slot with `count` versions from `firstId`, the newest `age` hours old.
export function makeSaveSlot(
  slot: string,
  count: number,
  age: number,
  firstId: number,
): SaveSchema[] {
  return Array.from({ length: count }).map((_, i) =>
    makeSave(firstId + i, slot, age + i * 26, {
      screenshot: saveScreenshot((i * 47 + slot.length * 31) % 360),
    }),
  );
}

// Autosave history, two named slots and two archives: the full slot model.
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
  return stateFixture({
    file_name: "state_1.state",
    file_name_no_tags: "state_1.state",
    file_name_no_ext: "state_1",
    file_path: "/states/snes",
    file_size_bytes: 524288,
    full_path: "/states/snes/state_1.state",
    download_path: "/api/states/1/content",
    created_at: hoursAgo(53 * 24),
    updated_at: WRITTEN_AT,
    emulator: "snes9x",
    screenshot: screenshotFixture(
      "https://placehold.co/640x360/2d2147/ffffff?text=Save+State",
    ),
    ...overrides,
  });
}

// Distinct placeholder shots so the strip can be scanned visually.
const stateShots: { color: string; label: string }[] = [
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

export function manyStates(n: number): StateSchema[] {
  const ages = [
    2,
    5,
    24,
    2 * 24,
    4 * 24,
    7 * 24,
    14 * 24,
    30 * 24,
    60 * 24,
    180 * 24,
  ];
  return Array.from({ length: n }).map((_, i) => {
    const shot = stateShots[i % stateShots.length];
    const at = hoursAgo(ages[i % ages.length]);
    return makeState({
      id: i + 1,
      file_name: `${shot.label.replace("+", " ").toLowerCase()}_${i + 1}.state`,
      file_size_bytes: 256 * 1024 + i * 73 * 1024,
      created_at: at,
      updated_at: at,
      screenshot: screenshotFixture(
        `https://placehold.co/640x360/${shot.color}/ffffff?text=${shot.label}`,
        i + 1,
      ),
      emulator: i % 3 === 0 ? "snes9x" : i % 3 === 1 ? "mesen" : null,
    });
  });
}

// Browser-player states share a long prefix, so only the tail tells them apart.
export function identicalPrefixStates(count: number): StateSchema[] {
  return Array.from({ length: count }).map((_, i) => {
    const tail = hoursAgo(i + 1);
    return makeState({
      id: i + 1,
      file_name: `${IDENTICAL_STATE_PREFIX}_${tail.replace(/[:.]/g, "-")}.state`,
      created_at: tail,
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
    user_updated_at: save.updated_at,
    ...overrides,
  };
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
    user_updated_at: state.updated_at,
    ...overrides,
  };
}

// User 1's saves plus another user's public ones.
export function mixedCommunitySaves(): UserSaveSchema[] {
  const mine = saveSlotLibrary().map((s) =>
    toUserSave(s, "player", { user_id: 1, is_public: s.id % 3 === 0 }),
  );
  const theirs = makeSaveSlot("shared_route", 2, 40, 100).map((s) =>
    toUserSave(s, "speedrunner42", { user_id: 2 }),
  );
  return [...mine, ...theirs];
}

export function mixedCommunityStates(): UserStateSchema[] {
  const mine = manyStates(4).map((s) =>
    toUserState(s, "player", { user_id: 1 }),
  );
  const theirs = manyStates(3).map((s, i) =>
    toUserState(
      { ...s, id: 50 + i, user_id: 3, emulator: "mesen" },
      "archivist",
    ),
  );
  return [...mine, ...theirs];
}

export function storyDetailedRom(
  overrides: Partial<DetailedRomSchema> = {},
): DetailedRomSchema {
  return makeDetailedRom({
    platform_slug: "snes",
    all_user_saves: mixedCommunitySaves(),
    all_user_states: mixedCommunityStates(),
    ...overrides,
  });
}
