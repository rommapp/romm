/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { DeviceSyncSchema } from './DeviceSyncSchema';
import type { ScreenshotSchema } from './ScreenshotSchema';
/**
 * A save enriched with its owner's username, for the community (My /
 * Community) view. Mirrors UserScreenshotSchema.
 */
export type UserSaveSchema = {
    /**
     * The ID of the sync channel the row was pushed into. Null means a backup the user manages.
     */
    channel_id?: (string | null);
    is_favorite?: boolean;
    /**
     * The owner's free-text labels.
     */
    labels?: Array<string>;
    id: number;
    rom_id: number;
    user_id: number;
    /**
     * The file name, extension included.
     */
    file_name: string;
    /**
     * The file name without its extension or any tags in parentheses or brackets.
     */
    file_name_no_tags: string;
    file_name_no_ext: string;
    file_extension: string;
    /**
     * The folder holding the file.
     */
    file_path: string;
    file_size_bytes: number;
    full_path: string;
    download_path: string;
    missing_from_fs: boolean;
    created_at: string;
    updated_at: string;
    emulator: (string | null);
    slot?: (string | null);
    content_hash?: (string | null);
    is_public?: boolean;
    screenshot: (ScreenshotSchema | null);
    origin_device_id?: (string | null);
    /**
     * The sync state of every device that synced the save, the named device first. Empty when the request names no device.
     */
    device_syncs?: Array<DeviceSyncSchema>;
    username: string;
    user_avatar_path?: string;
    user_updated_at?: (string | null);
};

