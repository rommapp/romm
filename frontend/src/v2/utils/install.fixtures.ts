import type {
  InstallCandidatesSchema,
  InstallSessionSchema,
  InstallSessionState,
  InstallStreamManifestSchema,
} from "@/__generated__";
import type {
  InstallCache,
  InstallCacheEntry,
  ProtonBuildExtended,
} from "@/services/api/install";

const TIMESTAMP = "2026-09-30T00:00:00Z";

export function makeInstallSession(
  state: InstallSessionState,
  overrides: Partial<InstallSessionSchema> = {},
): InstallSessionSchema {
  return {
    id: 1,
    rom_id: 1,
    user_id: 1,
    state,
    bytes_written: 0,
    bytes_total: 0,
    created_at: TIMESTAMP,
    updated_at: TIMESTAMP,
    ...overrides,
  };
}

export const protonBuilds: ProtonBuildExtended[] = [
  {
    id: "proton-cachyos",
    label: "Proton-CachyOS (latest)",
    installed: true,
    version: "10.0-20260915",
    size_bytes: 612_000_000,
  },
  {
    id: "ge-proton-9",
    label: "GE-Proton 9 (latest)",
    installed: false,
  },
  {
    id: "my-build",
    label: "My custom build",
    installed: true,
    custom: true,
    size_bytes: 540_000_000,
  },
];

export function makeCandidates(romId = 1): InstallCandidatesSchema {
  return {
    rom_id: romId,
    candidates: [
      {
        path: "setup.exe",
        file_name: "setup.exe",
        file_size_bytes: 2_400_000,
        rank: 1,
        kind: "installer",
      },
      {
        path: "extras/redist.exe",
        file_name: "redist.exe",
        file_size_bytes: 800_000,
        rank: 2,
        kind: "installer",
      },
    ],
    needs_manual_pick: false,
    stream_copy: false,
  };
}

export function makeManifest(romId = 1): InstallStreamManifestSchema {
  return {
    rom_id: romId,
    files: [],
    viewer_count: 0,
    download_speed_limit_bytes_per_sec: null,
  };
}

function makeCacheEntry(
  overrides: Partial<InstallCacheEntry>,
): InstallCacheEntry {
  return {
    session_id: 1,
    rom_id: 1,
    rom_name: "Example Game",
    platform_slug: "win",
    user_id: 1,
    state: "done",
    size_bytes: 3_200_000_000,
    created_at: TIMESTAMP,
    updated_at: TIMESTAMP,
    ...overrides,
  };
}

export const installCache: InstallCache = {
  total_bytes: 4_950_000_000,
  entries: [
    makeCacheEntry({}),
    makeCacheEntry({
      session_id: 2,
      rom_id: 2,
      rom_name: "Another Game",
      size_bytes: 1_750_000_000,
      state: "streaming",
    }),
  ],
};
