/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ChannelRefSchema } from './ChannelRefSchema';
import type { DeviceRefSchema } from './DeviceRefSchema';
import type { HeldBySchema } from './HeldBySchema';
import type { ScreenshotRefSchema } from './ScreenshotRefSchema';
import type { SnapshotKind } from './SnapshotKind';
import type { SnapshotSaveSchema } from './SnapshotSaveSchema';
import type { SnapshotStateSchema } from './SnapshotStateSchema';
export type SnapshotSchema = {
    id: number;
    digest: string;
    kind: SnapshotKind;
    parent_snapshot_id: (number | null);
    channel: (ChannelRefSchema | null);
    author_user_id: (number | null);
    device: (DeviceRefSchema | null);
    emulator: (string | null);
    rom_id: (number | null);
    rom_sha1: (string | null);
    save_target: (string | null);
    is_hardcore: boolean;
    is_pinned: boolean;
    is_public: boolean;
    created_at: string;
    held_by: Array<HeldBySchema>;
    save: (SnapshotSaveSchema | null);
    states: Record<string, Record<string, SnapshotStateSchema>>;
    thumbnail: (ScreenshotRefSchema | null);
};

