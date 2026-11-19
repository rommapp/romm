/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { DeviceSyncSchema } from './DeviceSyncSchema';
import type { ScreenshotSchema } from './ScreenshotSchema';
export type SaveSchema = {
    /**
     * The ID of the sync channel the row was pushed into. Null means a backup the user manages.
     */
    channel_id?: (string | null);
    /**
     * Whether the owner marked it as a favorite.
     */
    is_favorite?: boolean;
    /**
     * The owner's free-text labels.
     */
    labels?: Array<string>;
    /**
     * The internal ID.
     */
    id: number;
    /**
     * The internal ID of the rom.
     */
    rom_id: number;
    /**
     * The ID of the user who owns it.
     */
    user_id: number;
    /**
     * The file name, extension included.
     */
    file_name: string;
    /**
     * The file name without its extension or any tags in parentheses or brackets.
     */
    file_name_no_tags: string;
    /**
     * The file name without its extension.
     */
    file_name_no_ext: string;
    /**
     * The file extension.
     */
    file_extension: string;
    /**
     * The folder holding the file.
     */
    file_path: string;
    /**
     * The size of the file, in bytes.
     */
    file_size_bytes: number;
    /**
     * The path to the file on disk.
     */
    full_path: string;
    /**
     * The path to download the file from.
     */
    download_path: string;
    /**
     * True when the file is no longer on disk.
     */
    missing_from_fs: boolean;
    /**
     * When the record was created.
     */
    created_at: string;
    /**
     * When the record last changed.
     */
    updated_at: string;
    /**
     * The emulator that wrote the save.
     */
    emulator: (string | null);
    /**
     * The slot the save belongs to. Null for a save without a slot.
     */
    slot?: (string | null);
    /**
     * The hash of the save file's content.
     */
    content_hash?: (string | null);
    /**
     * Whether other users can see the save.
     */
    is_public?: boolean;
    /**
     * The screenshot stored with the save.
     */
    screenshot: (ScreenshotSchema | null);
    /**
     * The ID of the device the save came from.
     */
    origin_device_id?: (string | null);
    /**
     * The sync state of the device the request named.
     */
    device_syncs?: Array<DeviceSyncSchema>;
};

