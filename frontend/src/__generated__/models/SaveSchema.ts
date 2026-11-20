/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { DeviceSyncSchema } from './DeviceSyncSchema';
import type { ScreenshotSchema } from './ScreenshotSchema';
export type SaveSchema = {
    /**
     * The ID of the sync channel this was pushed to. Null for a backup that the user manages themselves.
     */
    channel_id?: (string | null);
    /**
     * MD5 of the file's bytes, or for a zip, of its sorted `name:md5` entry lines. Null for a file never hashed.
     */
    content_hash?: (string | null);
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
    is_public?: boolean;
    screenshot: (ScreenshotSchema | null);
    origin_device_id?: (string | null);
    /**
     * The sync state of each device that has synced the save, starting with the device given in `device_id`. Empty when the request has no `device_id`.
     */
    device_syncs?: Array<DeviceSyncSchema>;
};

