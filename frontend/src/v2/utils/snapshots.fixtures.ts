import type {
  ChannelSchema,
  DeviceRefSchema,
  SnapshotSchema,
  SnapshotStateSchema,
} from "@/__generated__";
import { hoursAgo } from "@/v2/utils/saveStates.fixtures";

export const ownDevice: DeviceRefSchema = {
  id: "odin",
  name: "Odin 3",
  client: "argosy",
  is_own: true,
};

export const otherUsersDevice: DeviceRefSchema = {
  id: null,
  name: null,
  client: null,
  is_own: false,
};

export function stateFixture(
  hash: string,
  over: Partial<SnapshotStateSchema> = {},
): SnapshotStateSchema {
  return {
    id: hash.length,
    file_name: `game.state.${hash}`,
    file_size_bytes: 1_048_576,
    content_hash: hash,
    emulator_version: null,
    core_version: null,
    download_path: `/api/states/${hash}/content`,
    screenshot: null,
    ...over,
  };
}

export function snapshotFixture(
  over: Partial<SnapshotSchema> = {},
): SnapshotSchema {
  return {
    id: 42,
    digest: "sha256:7c1e",
    kind: "channel",
    parent_snapshot_id: 41,
    channel: null,
    author_user_id: 1,
    device: ownDevice,
    emulator: "argosy",
    rom_id: 1,
    rom_sha1: "2d5d2e",
    save_target: null,
    is_hardcore: false,
    is_pinned: false,
    is_public: false,
    created_at: hoursAgo(2),
    held_by: [],
    save: {
      id: 1911,
      file_name: "save [2026-09-23_10-14-03-218].srm",
      file_size_bytes: 8192,
      content_hash: "9f2c",
      identity_hash: "9f2c",
      shape: "SINGLE",
      format: "native",
      emulator: "argosy",
      emulator_version: null,
      core: null,
      core_version: null,
      download_path: "/api/saves/1911/content",
      screenshot: null,
    },
    states: { snes9x: { auto: stateFixture("a1b2") } },
    thumbnail: null,
    ...over,
  };
}

export function channelFixture(
  over: Partial<ChannelSchema> = {},
): ChannelSchema {
  const current = "current" in over ? over.current : snapshotFixture();
  return {
    id: "0192f1c4-0000-7000-8000-000000000001",
    label: "default",
    is_public: false,
    is_hardcore: false,
    is_own: true,
    owner_username: "nendo",
    current_snapshot_id: current?.id ?? null,
    rom_id: 1,
    rom_file_id: 7,
    created_at: hoursAgo(24 * 8),
    updated_at: hoursAgo(2),
    snapshot_count: current ? 5 : 0,
    ...over,
    current: current ?? null,
  };
}
